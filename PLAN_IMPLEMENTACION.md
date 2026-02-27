# Plan de Implementación: Paridad Backend vs ERP Google Sheets (CEM Huánuco)

## Contexto

El Centro Especializado Mujer (CEM) opera con un Google Sheets como ERP que gestiona citas, turnos, CPN, laboratorio, patología, vacunas, comisiones e inventario. El backend actual (FastAPI + PostgreSQL + SQLAlchemy async) cubre ~60% de la operación real. Este plan cierra el 40% restante organizado en 6 hitos, asignado por roles de desarrollador, con archivos exactos a crear/modificar.

**Cobertura de los 23 gaps identificados en la auditoría → 100%**

---

## HITO 1: Fundamentos (Semanas 1-2)

> Cambios base que desbloquean los hitos siguientes: categorías de servicios, rol OBSTETRA, booked_by, FUR, seed del tarifario.

### Tarea 1.1 — Categorías + precio de costo en Service
**Rol: Backend Senior** | **Esfuerzo: 1 día** | **Gaps: #4, #12**

Agregar enum `ServiceCategory` (CONSULTATION, ECOGRAPHY, PROCEDURE, LAB_EXTERNAL, SURGERY, CPN, VACCINATION, OTHER), campo `cost_price Numeric(12,2)` y `code String(20)` al modelo Service.

**Archivos a modificar:**
- `app/models/service.py` — Agregar `ServiceCategory` enum, columnas `category`, `cost_price`, `code`, index `(clinic_id, category)`
- `app/schemas/service.py` — Agregar campos a Create/Update/Response
- `app/services/service_service.py` — Filtro por `category` en `list_services`
- `app/api/v1/services.py` — Query param `category` en GET list

**Migración:** `alembic/versions/xxxx_add_service_category_cost_price.py`

---

### Tarea 1.2 — Seed completo del tarifario (130+ servicios)
**Rol: Backend Junior** | **Esfuerzo: 2 días** | **Gap: #4**

CSV con los 130+ servicios del tarifario CEM y script de seed idempotente.

**Archivos a crear:**
- `data/service_tariff.csv` — Columnas: code, name, category, price, cost_price, duration_minutes, color
- `scripts/seed_services.py` — Lee CSV, upsert por (clinic_id, name)

---

### Tarea 1.3 — Rol OBSTETRA en RBAC
**Rol: Backend Senior** | **Esfuerzo: 1 día** | **Gap: #11**

Agregar `OBSTETRA = "obstetra"` al enum `UserRole`. Permisos: igual que DOCTOR para pacientes, citas, prenatal, lab; sin acceso a invoices ni admin.

**Archivos a modificar:**
- `app/models/user.py` — Agregar valor al enum
- `app/auth/dependencies.py` o `app/auth/rbac.py` — Actualizar mapas de permisos
- Rutas que usan `require_role`: `appointments.py`, `patients.py`, `records.py`, `prenatal.py`, `lab.py`, `reports.py`, `staff_schedules.py` — Agregar OBSTETRA donde está DOCTOR

**Migración:** `alembic/versions/xxxx_add_obstetra_role.py` — `ALTER TYPE userrole ADD VALUE 'obstetra'`

---

### Tarea 1.4 — Campo `booked_by` en Appointment
**Rol: Backend Mid** | **Esfuerzo: 0.5 días** | **Gap: #5**

Registrar qué usuario creó la cita.

**Archivos a modificar:**
- `app/models/appointment.py` — Agregar `booked_by: Mapped[uuid.UUID | None]` FK users.id, relationship `booker`
- `app/schemas/appointment.py` — Agregar a Response
- `app/services/appointment_service.py` — Setear `booked_by=user_id` en `create_appointment`

**Migración:** `alembic/versions/xxxx_add_appointment_booked_by.py`

---

### Tarea 1.5 — FUR y cálculo de semanas gestacionales
**Rol: Backend Mid** | **Esfuerzo: 1 día** | **Gap: #15**

Agregar `fur` (Date) al modelo Patient. Property `gestational_weeks` calculada. Auto-cálculo en PrenatalVisit.

**Archivos a modificar:**
- `app/models/patient.py` — Agregar `fur: Mapped[date | None]`
- `app/schemas/patient.py` — Agregar `fur` y `gestational_weeks` (computed) a Response
- `app/services/prenatal_service.py` — Auto-calcular semana gestacional desde FUR si no se provee

**Migración:** `alembic/versions/xxxx_add_patient_fur.py`

---

### Criterios de aceptación Hito 1:
- [ ] GET /services soporta `?category=ECOGRAPHY`
- [ ] ServiceResponse incluye `category`, `cost_price`, `code`
- [ ] 130+ servicios seedeados con script
- [ ] Usuario con rol `obstetra` puede crear visitas prenatales y citas, no puede anular facturas
- [ ] Toda cita nueva tiene `booked_by` con el ID del usuario que la creó
- [ ] Paciente con FUR retorna `gestational_weeks` en response

---

## HITO 2: Paquetes CPN + Pagos en Cuotas (Semanas 2-4)

> El core del negocio obstétrico: paquetes de servicios con pagos fraccionados y cronograma automático de controles.

### Tarea 2.1 — Modelos ServicePackage + PackageItem
**Rol: Backend Senior** | **Esfuerzo: 2 días** | **Gap: #1**

**Archivos a crear:**
- `app/models/service_package.py`:
  - `ServicePackage`: id, clinic_id, name, description, total_price(Numeric 12,2), valid_from_week(SmallInteger nullable), is_active, auto_schedule(Boolean), created_at, updated_at
  - `PackageItem`: id, package_id(FK), service_id(FK), quantity(Integer default 1), description_override(String nullable), gestational_week_target(SmallInteger nullable)
- `app/schemas/service_package.py` — Create/Update/Response para ambos
- `app/services/service_package_service.py` — CRUD paquetes con items incluidos
- `app/api/v1/service_packages.py` — Router: POST, GET list, GET detail, PATCH, DELETE(soft)

**Archivos a modificar:**
- `app/models/__init__.py` — Registrar ServicePackage, PackageItem
- `app/api/v1/router.py` — Registrar bajo `/packages`

**Migración:** `alembic/versions/xxxx_create_service_packages.py`

---

### Tarea 2.2 — Modelos PatientPackage + PackagePayment
**Rol: Backend Senior** | **Esfuerzo: 2 días** | **Gaps: #1, #2**

Inscripción de paciente en paquete + pagos parciales.

**Archivos a crear:**
- `app/models/patient_package.py`:
  - `PatientPackageStatus`: ACTIVE, COMPLETED, CANCELLED
  - `PatientPackage`: id, clinic_id, patient_id(FK), package_id(FK), enrolled_by(FK users), total_amount, amount_paid(default 0), balance(computed), status, enrolled_at, completed_at, notes
  - `PackagePayment`: id, patient_package_id(FK), clinic_id, amount(Numeric 12,2), payment_method(reusar PaymentMethod de cash_register), cash_movement_id(FK nullable), invoice_id(FK nullable), paid_at, notes, created_by(FK users)
- `app/schemas/patient_package.py`
- `app/services/patient_package_service.py`:
  - `enroll_patient()` — Crea PatientPackage, auto-genera citas si auto_schedule=True
  - `register_payment()` — Crea PackagePayment, actualiza amount_paid/balance, auto-completa si balance=0
  - `list_patient_packages()` — Con historial de pagos
  - `get_package_detail()` — Detalle con items consumidos vs pendientes
- `app/api/v1/patient_packages.py`

**Archivos a modificar:**
- `app/models/__init__.py`, `app/api/v1/router.py`

**Migración:** `alembic/versions/xxxx_create_patient_packages.py`

---

### Tarea 2.3 — Auto-generación de cronograma CPN
**Rol: Backend Mid** | **Esfuerzo: 1.5 días** | **Gap: #1**

Al inscribir paciente en paquete CPN con `auto_schedule=True`, generar citas automáticas según semanas gestacionales target de cada PackageItem, calculando fechas desde FUR de la paciente.

**Archivos a modificar:**
- `app/services/patient_package_service.py` — Función `_auto_schedule_cpn_controls(db, patient, patient_package)` invocada en `enroll_patient()`

---

### Tarea 2.4 — Seed de paquetes CPN
**Rol: Backend Junior** | **Esfuerzo: 0.5 días** | **Gap: #1**

**Archivos a crear:**
- `scripts/seed_cpn_packages.py` — Paquete A (S/1500, desde 6 sem, 8 consultas + eco genética + eco morfológica + 3 ecos rutina + panel lab), Paquete B (S/950, desde 15 sem, 5 consultas + eco morfo + 2 ecos rutina + panel lab)

---

### Criterios de aceptación Hito 2:
- [ ] Admin puede crear paquetes de servicios con items incluidos
- [ ] Recepcionista puede inscribir paciente en paquete CPN
- [ ] Se pueden registrar múltiples pagos parciales; balance se actualiza automáticamente
- [ ] Cuando balance = 0, status cambia a COMPLETED
- [ ] Inscripción CPN con auto_schedule genera citas prenatales basadas en FUR
- [ ] GET /patients/{id}/packages retorna paquetes con historial de pagos

---

## HITO 3: Comisiones Médicas + Cuentas por Cobrar/Pagar (Semanas 4-6)

> Tracking financiero: cuánto se le debe a cada médico y cuánto deben los pacientes/proveedores.

### Tarea 3.1 — Modelos de comisiones + auto-generación
**Rol: Backend Senior** | **Esfuerzo: 1.5 días** | **Gap: #3**

**Archivos a crear:**
- `app/models/commission.py`:
  - `CommissionType`: PERCENTAGE, FIXED
  - `CommissionRule`: id, clinic_id, doctor_id(FK nullable=null es default para todos), service_id(FK), commission_type, value(Numeric 12,2), is_active. Unique: (clinic_id, doctor_id, service_id)
  - `CommissionEntryStatus`: PENDING, PAID
  - `CommissionEntry`: id, clinic_id, doctor_id(FK), appointment_id(FK nullable), service_id(FK), patient_id(FK), service_amount, commission_amount, status, period(String "2026-02"), paid_at, paid_reference, created_at
- `app/schemas/commission.py`
- `app/services/commission_service.py`:
  - CRUD para rules
  - `generate_commission_entry()` — Llamada cuando cita pasa a COMPLETED
  - `get_liquidation()` — Suma comisiones por doctor/período
  - `mark_as_paid()` — Marca lote como pagado
- `app/api/v1/commissions.py`

**Archivos a modificar:**
- `app/services/appointment_service.py` — En `change_status` cuando status=COMPLETED, llamar `commission_service.generate_commission_entry()`
- `app/models/__init__.py`, `app/api/v1/router.py`

**Migración:** `alembic/versions/xxxx_create_commission_tables.py`

---

### Tarea 3.2 — Reportes de producción médica + comisiones
**Rol: Backend Mid** | **Esfuerzo: 1.5 días** | **Gaps: #13, #20**

**Archivos a modificar:**
- `app/services/report_service.py`:
  - `get_doctor_production_report(clinic_id, date_from, date_to)` — Servicios por doctor, ingresos atribuidos
  - `get_commission_liquidation_report(clinic_id, period, doctor_id)` — Comisiones pendientes/pagadas
  - `get_doctor_shift_count(clinic_id, year, month)` — Turnos trabajados por doctor
- `app/schemas/report.py` — Schemas: DoctorProductionReport, CommissionLiquidationReport, DoctorShiftCountReport
- `app/api/v1/reports.py` — Endpoints: GET /reports/doctor-production, GET /reports/commission-liquidation, GET /reports/doctor-shifts

---

### Tarea 3.3 — Cuentas por Cobrar y por Pagar
**Rol: Backend Senior** | **Esfuerzo: 2 días** | **Gap: #9**

**Archivos a crear:**
- `app/models/accounts.py`:
  - `AccountReceivable`: id, clinic_id, patient_id(FK), description, total_amount, amount_paid, balance, due_date(Date nullable), reference_type(String: "package"/"invoice"), reference_id(UUID), status(PENDING/PARTIAL/PAID/OVERDUE), created_at, updated_at
  - `ARPayment`: id, receivable_id(FK), amount, payment_method, cash_movement_id(FK nullable), paid_at, notes, created_by(FK)
  - `AccountPayable`: id, clinic_id, supplier_id(FK), description, total_amount, amount_paid, balance, due_date, reference, status, created_at, updated_at
  - `APPayment`: id, payable_id(FK), amount, payment_method, cash_movement_id(FK nullable), paid_at, notes, created_by(FK)
- `app/schemas/accounts.py`
- `app/services/accounts_service.py` — CRUD + pagos parciales + auto-crear receivable al inscribir paquete con balance
- `app/api/v1/accounts.py`

**Archivos a modificar:**
- `app/services/patient_package_service.py` — Al inscribir paquete, si balance > 0, crear AccountReceivable
- `app/models/__init__.py`, `app/api/v1/router.py`

**Migración:** `alembic/versions/xxxx_create_accounts_tables.py`

---

### Criterios de aceptación Hito 3:
- [ ] Admin configura reglas de comisión por servicio (% o fijo), opcionalmente por doctor
- [ ] Al completar una cita, se genera automáticamente un CommissionEntry
- [ ] GET /reports/commission-liquidation?period=2026-02 retorna totales por doctor
- [ ] Se pueden marcar comisiones como pagadas
- [ ] AccountReceivable se crea automáticamente al inscribir paquete con balance > 0
- [ ] AccountPayable se puede crear manualmente para deudas con proveedores
- [ ] Ambas cuentas soportan pagos parciales

---

## HITO 4: Turnos Generalizados + Calendario Mensual + Códigos Lab (Semanas 5-7)

> Scheduling para todo el personal, vista de rol mensual, códigos secuenciales de patología/citología.

### Tarea 4.1 — StaffSchedule generalizado
**Rol: Backend Senior** | **Esfuerzo: 1.5 días** | **Gap: #8**

Crear tabla `StaffSchedule` paralela a `DoctorSchedule` para personal no-médico (obstetras, recepcionistas, lab). DoctorSchedule se mantiene intacto para cálculo de slots.

**Archivos a crear:**
- `app/models/staff_schedule.py`:
  - `StaffSchedule`: id, clinic_id, user_id(FK), day_of_week(SmallInteger 0-6), start_time(Time), end_time(Time), shift_label(String "mañana"/"tarde"), is_active

**Archivos a modificar:**
- `app/services/staff_schedule_service.py` — CRUD para StaffSchedule
- `app/api/v1/staff_schedules.py` — Endpoints para turnos de staff
- `app/models/__init__.py`

**Migración:** `alembic/versions/xxxx_create_staff_schedules.py`

---

### Tarea 4.2 — Endpoint de calendario mensual (Rol Médico)
**Rol: Backend Mid** | **Esfuerzo: 1 día** | **Gap: #10**

Genera vista mensual combinando DoctorSchedule + StaffSchedule + StaffScheduleOverride.

**Archivos a modificar:**
- `app/services/staff_schedule_service.py` — `get_monthly_calendar(clinic_id, year, month)`: genera todos los días del mes, lookup day_of_week, aplica overrides, retorna `[{date, user_id, user_name, role, clinic_name, start_time, end_time}]`
- `app/schemas/staff_schedule.py` — `MonthlyCalendarDay`, `MonthlyCalendarResponse`
- `app/api/v1/staff_schedules.py` — `GET /staff-schedules/calendar?year=2026&month=3`

---

### Tarea 4.3 — Códigos secuenciales de lab (M26-XX, C26-XX) + cassette_count
**Rol: Backend Mid** | **Esfuerzo: 1 día** | **Gaps: #6, #21**

**Archivos a crear:**
- `app/models/lab_sequence.py`:
  - `LabSequence`: id, clinic_id, sequence_type("pathology"/"cytology"), year(SmallInteger), last_number(Integer default 0). Unique: (clinic_id, sequence_type, year)

**Archivos a modificar:**
- `app/models/lab_order.py` — Agregar `lab_code: Mapped[str | None]` String(20), `cassette_count: Mapped[int | None]` SmallInteger
- `app/services/lab_service.py` — En `create_order`, si study_type es PATHOLOGY/CYTOLOGY, generar código con `SELECT FOR UPDATE` para concurrencia
- `app/schemas/lab.py` — Agregar `lab_code`, `cassette_count` a Response/Create

**Migración:** `alembic/versions/xxxx_add_lab_codes_and_sequences.py`

---

### Tarea 4.4 — Canal de entrega de resultados
**Rol: Backend Junior** | **Esfuerzo: 0.5 días** | **Gap: #17**

**Archivos a modificar:**
- `app/models/lab_order.py` — Agregar `DeliveryChannel` enum (WHATSAPP, PRINTED, IN_PERSON, EMAIL, NOT_DELIVERED), columna `delivery_channel`, `delivered_by`(FK users nullable)
- `app/schemas/lab.py` — Agregar a Update y Response
- `app/services/lab_service.py` — Manejar en update_order

**Migración:** `alembic/versions/xxxx_add_lab_delivery_channel.py`

---

### Criterios de aceptación Hito 4:
- [ ] Obstetras y recepcionistas pueden tener turnos semanales configurados
- [ ] GET /staff-schedules/calendar?year=2026&month=3 retorna grilla mensual completa
- [ ] Nuevas órdenes de patología reciben código M26-01, M26-02...
- [ ] Nuevas órdenes de citología reciben código C26-01, C26-02...
- [ ] LabOrder muestra `delivery_channel` y `cassette_count`

---

## HITO 5: WhatsApp + Recordatorios Automáticos + Procedimiento→Insumos (Semanas 7-9)

> Comunicación moderna y vinculación de procedimientos con inventario.

### Tarea 5.1 — Integración WhatsApp Business API
**Rol: Backend Senior** | **Esfuerzo: 2.5 días** | **Gap: #7**

**Archivos a crear:**
- `app/services/whatsapp_service.py` — Integración con Meta Cloud API: `send_template(phone, template, params)`, `send_text(phone, message)`
- `app/services/messaging_service.py` — Fachada unificada: `send_notification(phone, message, channel="whatsapp")`, fallback a SMS
- `app/api/v1/messaging.py` — Router: enviar mensaje, historial

**Archivos a modificar:**
- `app/config.py` — Agregar WHATSAPP_API_URL, WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID
- `app/models/sms_message.py` — Agregar `MessageChannel` enum (SMS, WHATSAPP, EMAIL), columna `channel`
- `app/api/v1/router.py` — Registrar `/messaging`

**Migración:** `alembic/versions/xxxx_add_message_channel.py`

---

### Tarea 5.2 — Recordatorios automáticos de citas (Celery)
**Rol: Backend Senior** | **Esfuerzo: 2 días** | **Gap: #19**

Tarea periódica Celery que envía recordatorios 24h antes por WhatsApp/SMS.

**Archivos a crear:**
- `app/tasks/__init__.py`
- `app/tasks/celery_app.py` — Config Celery con Redis broker
- `app/tasks/reminders.py` — `send_appointment_reminders()`: query citas 24h adelante, enviar via messaging_service, marcar `reminder_sent_at`

**Archivos a modificar:**
- `app/models/appointment.py` — Agregar `reminder_sent_at: Mapped[datetime | None]`

**Migración:** `alembic/versions/xxxx_add_appointment_reminder_sent.py`

---

### Tarea 5.3 — Vínculo Procedimiento → Insumos consumidos
**Rol: Backend Mid** | **Esfuerzo: 1.5 días** | **Gap: #16**

Mapeo de servicios a items de inventario. Al completar cita, auto-descontar stock.

**Archivos a crear:**
- `app/models/procedure_supply.py`:
  - `ProcedureSupply`: id, clinic_id, service_id(FK), item_id(FK inventory_items), quantity(Numeric 12,2), is_active. Unique: (clinic_id, service_id, item_id)
- `app/schemas/procedure_supply.py`
- `app/services/procedure_supply_service.py` — CRUD + `auto_deduct_supplies()` que crea StockMovement EXIT
- `app/api/v1/procedure_supplies.py`

**Archivos a modificar:**
- `app/services/appointment_service.py` — En `change_status` a COMPLETED, llamar `auto_deduct_supplies()`
- `app/models/__init__.py`, `app/api/v1/router.py`

**Migración:** `alembic/versions/xxxx_create_procedure_supplies.py`

---

### Criterios de aceptación Hito 5:
- [ ] Se pueden enviar mensajes por WhatsApp via Meta Cloud API con fallback a SMS
- [ ] Tarea Celery envía recordatorios 24h antes sin duplicados
- [ ] Admin configura qué insumos consume cada procedimiento
- [ ] Al completar cita de procedimiento, inventario se descuenta automáticamente con StockMovement

---

## HITO 6: Dashboards, Vacunación, Variantes y Conciliación (Semanas 8-10)

> Polish final: reportes comparativos, módulo de vacunas, variantes de precio, conciliación bancaria.

### Tarea 6.1 — Dashboard comparativo por sede
**Rol: Backend Mid** | **Esfuerzo: 1.5 días** | **Gap: #18**

**Archivos a modificar:**
- `app/services/report_service.py` — `get_comparative_dashboard(org_id, date_from, date_to)`: ingresos, visitas, pacientes agrupados por clinic_id
- `app/schemas/report.py` — `ClinicComparison`, `ComparativeDashboardResponse`
- `app/api/v1/reports.py` — `GET /reports/comparative-dashboard` (ORG_ADMIN+)

---

### Tarea 6.2 — Módulo de vacunación
**Rol: Backend Mid** | **Esfuerzo: 2 días** | **Gap: #14**

**Archivos a crear:**
- `app/models/vaccination.py`:
  - `VaccineScheme`: id, name, doses_total(int), dose_intervals_months(JSONB [0,2,6]), notes, is_active
  - `PatientVaccination`: id, clinic_id, patient_id(FK), vaccine_scheme_id(FK), dose_number(int), administered_at, administered_by(FK users), lot_number(String), next_dose_date(Date nullable), inventory_item_id(FK nullable), notes
- `app/schemas/vaccination.py`
- `app/services/vaccination_service.py` — Registrar dosis, auto-calcular next_dose_date, listar historial, verificar vencidos
- `app/api/v1/vaccinations.py`
- `scripts/seed_vaccine_schemes.py` — Gardasil (3 dosis: 0, 2, 6 meses), etc.

**Archivos a modificar:**
- `app/models/__init__.py`, `app/api/v1/router.py`

**Migración:** `alembic/versions/xxxx_create_vaccination_tables.py`

---

### Tarea 6.3 — Variantes de precio de servicios
**Rol: Backend Junior** | **Esfuerzo: 1 día** | **Gap: #22**

**Archivos a crear:**
- `app/models/service_variant.py`:
  - `ServicePriceVariant`: id, clinic_id, service_id(FK), label("Gemelar", "Fin de semana"), modifier_type(FIXED_SURCHARGE/PERCENTAGE_SURCHARGE), modifier_value(Numeric 12,2), is_active
- `app/schemas/service_variant.py`

**Archivos a modificar:**
- `app/services/service_service.py` — Incluir variantes en detalle de servicio
- `app/models/__init__.py`

**Migración:** `alembic/versions/xxxx_create_service_variants.py`

---

### Tarea 6.4 — Conciliación bancaria Yape/transferencias
**Rol: Backend Mid** | **Esfuerzo: 1 día** | **Gap: #23**

**Archivos a crear:**
- `app/models/bank_reconciliation.py`:
  - `ReconciliationStatus`: PENDING, MATCHED, DISCREPANCY
  - `BankReconciliation`: id, clinic_id, cash_movement_id(FK), expected_amount, actual_amount(nullable), status, bank_reference, reconciled_at, reconciled_by(FK), notes
- `app/schemas/bank_reconciliation.py`
- `app/services/bank_reconciliation_service.py`
- `app/api/v1/bank_reconciliation.py`

**Archivos a modificar:**
- `app/models/__init__.py`, `app/api/v1/router.py`

**Migración:** `alembic/versions/xxxx_create_bank_reconciliation.py`

---

### Criterios de aceptación Hito 6:
- [ ] ORG_ADMIN ve comparativa de ingresos/visitas entre sedes
- [ ] Se pueden configurar esquemas de vacunas y registrar dosis por paciente
- [ ] Next_dose_date se calcula automáticamente
- [ ] Servicios pueden tener variantes de precio (gemelar, fin de semana)
- [ ] Pagos digitales se pueden conciliar contra extractos bancarios

---

## Grafo de Dependencias

```
HITO 1 (fundamentos)
  ├──→ HITO 2 (paquetes CPN + cuotas)
  ├──→ HITO 3 (comisiones + cuentas)     ← depende parcialmente de H2 (auto-crear receivable)
  ├──→ HITO 4 (turnos + lab codes)
  └──→ HITO 5 (WhatsApp + reminders)
            └──→ HITO 6 (dashboards + vacunas + variantes)
```

**H2, H3, H4 pueden ejecutarse en paralelo** con diferentes devs una vez completado H1.

---

## Resumen de Esfuerzo por Rol

| Hito | Total Días | Backend Senior | Backend Mid | Backend Junior |
|------|-----------|---------------|-------------|----------------|
| H1: Fundamentos | 5.5 | 2 | 1.5 | 2 |
| H2: Paquetes + Cuotas | 6 | 4 | 1.5 | 0.5 |
| H3: Comisiones + Cuentas | 5 | 3.5 | 1.5 | 0 |
| H4: Turnos + Lab Codes | 4 | 1.5 | 2 | 0.5 |
| H5: WhatsApp + Inventario | 6 | 4.5 | 1.5 | 0 |
| H6: Dashboards + Vacunas | 5.5 | 0 | 4.5 | 1 |
| **TOTAL** | **32 días** | **15.5 días** | **13 días** | **4 días** |

**Con equipo de 3 devs en paralelo: ~10-12 semanas calendario.**
**Con equipo de 2 devs: ~14-16 semanas.**

---

## Cobertura de Gaps

| Gap | Descripción | Hito | Tarea |
|-----|------------|------|-------|
| #1 | Paquetes CPN | H2 | 2.1-2.4 |
| #2 | Pagos en cuotas | H2 | 2.2 |
| #3 | Comisiones médicas | H3 | 3.1, 3.2 |
| #4 | Categorías de servicios + seed | H1 | 1.1, 1.2 |
| #5 | Appointment booked_by | H1 | 1.4 |
| #6 | Códigos secuenciales lab | H4 | 4.3 |
| #7 | WhatsApp integration | H5 | 5.1 |
| #8 | StaffSchedule generalizado | H4 | 4.1 |
| #9 | Cuentas por cobrar/pagar | H3 | 3.3 |
| #10 | Calendario mensual | H4 | 4.2 |
| #11 | Rol OBSTETRA | H1 | 1.3 |
| #12 | Doble precio (costo/venta) | H1 | 1.1 |
| #13 | Reporte producción médica | H3 | 3.2 |
| #14 | Módulo vacunación | H6 | 6.2 |
| #15 | FUR + semanas gestacionales | H1 | 1.5 |
| #16 | Procedimiento → insumos | H5 | 5.3 |
| #17 | Canal entrega resultados | H4 | 4.4 |
| #18 | Dashboard comparativo sedes | H6 | 6.1 |
| #19 | Recordatorios automáticos | H5 | 5.2 |
| #20 | Conteo turnos mensuales | H3 | 3.2 |
| #21 | Cassette count patología | H4 | 4.3 |
| #22 | Variantes de precio | H6 | 6.3 |
| #23 | Conciliación bancaria | H6 | 6.4 |

**23/23 gaps cubiertos = 100% paridad con ERP.**

---

## Verificación

Para cada hito, después de implementar:

1. **Migración:** `alembic upgrade head` sin errores
2. **Servidor:** `uvicorn app.main:app --reload` arranca correctamente
3. **Endpoints:** Verificar cada endpoint nuevo con `curl` o Swagger UI (`/docs`)
4. **Seed:** Ejecutar scripts de seed y verificar datos en DB
5. **Integración:** Verificar que hooks en `appointment_service.change_status` disparan comisiones y descuento de inventario correctamente
6. **RBAC:** Verificar que rol OBSTETRA tiene acceso correcto (puede crear prenatal, no puede anular factura)
