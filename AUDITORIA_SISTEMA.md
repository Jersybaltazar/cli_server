# AUDITORÍA COMPLETA: Backend SaaS Clínicas vs ERP Google Sheets (CEM Huánuco)

**Fecha:** 23 de febrero de 2026
**Documento:** Comparativa del sistema backend actual contra la operación real del Centro Especializado Mujer (CEM) con sedes Huánuco (Huallayco) y Portales.

---

## RESUMEN EJECUTIVO

| Categoría | Estado |
|-----------|--------|
| Módulos implementados que cubren el ERP | **14 de 22** |
| Módulos parcialmente cubiertos | **5** |
| Módulos completamente faltantes | **3** |
| Cobertura funcional estimada | **~60%** |
| Prioridad para producción | **ALTA** — el negocio opera diariamente |

---

## 1. GESTIÓN DE CITAS (Pestañas: CITA Hco, CITA PORTALES)

### Lo que hace el ERP (Google Sheets):
- Agenda semanal por sede (Huallayco y Portales)
- Campos: hora, paciente, servicio, médico, celular, observación, responsable de agendamiento
- Estado de llegada del paciente ("LLEGÓ")
- Adelantos de pago registrados en observaciones ("ADELANTO 20 EL 21/02")
- Códigos de responsable: SCR (Sandra), FMA (Fiorella), NCS (Nataly), YCR (Yamilet), MDZB
- Vista diaria dividida en turnos mañana (8-2 PM) y tarde (2-8 PM)
- Médico de turno visible por día

### Lo que tiene el backend:
- ✅ CRUD de citas con estado (scheduled → confirmed → in_progress → completed/cancelled/no_show)
- ✅ Disponibilidad por médico y fecha
- ✅ Agenda diaria (`GET /appointments/agenda`)
- ✅ Booking público sin autenticación
- ✅ Relación paciente-médico-servicio
- ✅ Notas/observaciones en la cita

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 1.1 | **Campo "responsable de agendamiento"** | ALTA | El ERP registra quién agendó la cita (Sandra, Fiorella, etc.). El backend no tiene un campo `booked_by` o `created_by_user_id` en el modelo Appointment. |
| 1.2 | **Registro de adelantos de pago** | ALTA | El ERP anota adelantos en observaciones. El backend no tiene concepto de "pago parcial" o "anticipo" vinculado a la cita. |
| 1.3 | **Vista por sede** | MEDIA | El backend soporta multi-clínica, pero no hay concepto de "sede" dentro de una misma clínica. CEM opera como una organización con 2 sedes. Esto YA se resuelve con el modelo Organization → Clinic (cada sede = 1 clinic). |
| 1.4 | **Médico de turno del día** | MEDIA | El ERP muestra qué médico está de turno cada día. El backend tiene `DoctorSchedule` pero no un endpoint que diga "médico de turno hoy". |
| 1.5 | **Estado "LLEGÓ"** | BAJA | Equivale a pasar de `confirmed` → `in_progress`. Ya cubierto por la máquina de estados, solo falta que el frontend lo use. |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (80%)

---

## 2. ROLES MÉDICOS / TURNOS (Pestañas: ROL-MED, ROL MED 2)

### Lo que hace el ERP:
- Calendario mensual con turnos Mañana (8-2) y Tarde (2-8) por médico
- 9 médicos con abreviaturas: RR, DL, DIPA, JP, TY, AF, OCH, ES, DJ
- Distribución por sede (Portales vs Huallayco)
- Conteo de turnos por médico al mes
- Días libres marcados con "X"

### Lo que tiene el backend:
- ✅ `DoctorSchedule`: horarios recurrentes semanales (día, hora inicio, hora fin)
- ✅ `StaffScheduleOverride`: excepciones (vacaciones, feriados, cambios de turno)
- ✅ Campo `substitute_user_id` para reemplazos

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 2.1 | **Vista de rol mensual** | ALTA | No hay endpoint que genere la vista de calendario mensual de turnos tipo "ROL MED". Solo hay horarios recurrentes semanales. |
| 2.2 | **Asignación por sede por día** | ALTA | Un médico puede estar en Huallayco por la mañana y Portales por la tarde. El modelo actual asigna el doctor a UNA clínica. Se necesita `UserClinicAccess` + schedule por clínica. |
| 2.3 | **Conteo de turnos mensuales** | BAJA | Reportería de cuántos turnos trabajó cada médico. No existe como endpoint de reporte. |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (65%)

---

## 3. CONTROL PRENATAL - CPN (Pestañas: CPN-2025, CPN/CITA, ECO-CPN, CPN PARTICULARES)

### Lo que hace el ERP:
- Registro de pacientes CPN con: nombre, teléfono, tipo de paquete (A o B), FUR/Eco, semanas de gestación
- Cronograma de controles: 6-8ss, 10ss, 12ss (genética), 16ss, 17-18ss (revelación), 20ss, 22ss (morfológica), 24ss+
- Precios: Paquete A = S/1,500 (desde 6 sem), Paquete B = S/950 (desde 15 sem)
- Coordinación de citas CPN con obstetras (Anali, Janeth, Sandy)
- Estado de pagos por cuotas
- Seguimiento de ecografías programadas vs realizadas
- ~14 pacientes activas

### Lo que tiene el backend:
- ✅ `PrenatalVisit`: registro de visitas con semana gestacional, peso, PA, altura uterina, FCF, presentación, movimientos fetales, edema, labs
- ✅ Estándar CLAP/SIP
- ✅ Modelo `Service` con precios para crear paquetes CPN

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 3.1 | **Modelo de Paquete CPN** | CRÍTICA | No existe entidad "Paquete" que agrupe servicios con precio total, seguimiento de cuotas pagadas, y cronograma de controles. El ERP maneja paquetes A y B con pagos fraccionados. |
| 3.2 | **Cronograma automático de controles** | ALTA | Al registrar una paciente CPN con su FUR, el sistema debería generar automáticamente las fechas de cada control y ecografía. |
| 3.3 | **Seguimiento de ecografías programadas** | ALTA | El ERP marca cuáles ecografías se realizaron y cuáles faltan. No hay concepto de "checklist de servicios incluidos en paquete". |
| 3.4 | **Asignación de obstetra CPN** | MEDIA | Las pacientes CPN tienen una obstetra asignada (Anali, Janeth, Sandy) distinta al médico. No hay rol "OBSTETRA" en el sistema. |
| 3.5 | **FUR y cálculo de semanas gestacionales** | MEDIA | No hay campo FUR (Fecha de Última Regla) en Patient ni lógica para calcular automáticamente las semanas de gestación. |
| 3.6 | **Paquete gemelar** | BAJA | Precios diferenciados para embarazos gemelares (Paq A: S/1,900, Paq B: S/1,400). |

### VEREDICTO: ⚠️ PARCIALMENTE CUBIERTO (40%) — Módulo crítico para CEM

---

## 4. TARIFARIO / CATÁLOGO DE SERVICIOS (Pestaña: TARIFARIO CEM)

### Lo que hace el ERP:
- **130+ servicios** organizados por categoría:
  - Consultas especializadas (ginecología, obstetricia, cardiología, neumología, oftalmología)
  - Ecografías (15+ tipos con precios diferenciados)
  - Procedimientos menores (30+ tipos)
  - Control prenatal (paquetes)
  - Cirugías (15+ tipos, precios incluyen pre-quirúrgicos)
  - Laboratorio (60+ exámenes con precios individuales)
- Precios en soles (S/)
- Notas sobre qué incluye cada servicio

### Lo que tiene el backend:
- ✅ Modelo `Service`: name, description, duration_minutes, price, color, is_active
- ✅ CRUD completo de servicios

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 4.1 | **Categorización de servicios** | ALTA | El modelo Service no tiene `category` ni `subcategory`. El ERP tiene: Consultas, Ecografías, Procedimientos, Cirugías, Laboratorio, CPN. |
| 4.2 | **Servicios compuestos (paquetes)** | ALTA | No hay forma de crear un "paquete" que agrupe múltiples servicios con precio total (ej: "Paquete Ginecológico Integral" = consulta + eco TV + eco mama + PAP = S/320). |
| 4.3 | **Variantes de precio** | MEDIA | Algunos servicios tienen variantes (ej: "Eco gemelar" = +S/70). No hay soporte para variantes de un mismo servicio. |
| 4.4 | **Pre-carga del tarifario CEM** | ALTA | Los 130+ servicios del tarifario deben ser cargados como data semilla (seed). Actualmente no hay seed de servicios. |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (50%)

---

## 5. PAGOS A DOCTORES / COMISIONES (Pestaña: PAGOS DRS)

### Lo que hace el ERP:
- Tabla de comisiones por tipo de servicio realizado
- Ejemplos: Consulta = S/50, Eco básica = S/50, Eco especializada = S/130, Cesárea = S/1,200
- Pagos diferenciados por médico (Dr. Montes cardio, Dr. Tito Yepes ecografías)
- Diferencia entre "cobrar al paciente" vs "pagar al doctor"

### Lo que tiene el backend:
- ❌ **NO EXISTE** módulo de comisiones médicas

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 5.1 | **Modelo de comisiones médicas** | CRÍTICA | Necesita: servicio, monto comisión, médico (o default por servicio), método de cálculo (fijo o porcentaje). |
| 5.2 | **Liquidación de pagos a doctores** | ALTA | Reporte periódico de cuánto se le debe a cada médico por servicios realizados. |
| 5.3 | **Registro de pagos realizados** | ALTA | Historial de pagos efectuados a cada médico con fecha, monto, período. |

### VEREDICTO: ❌ NO IMPLEMENTADO — Módulo nuevo requerido

---

## 6. LABORATORIO (Pestañas: LAB CEM, XAMIRA)

### Lo que hace el ERP:
- **LAB CEM** (laboratorio interno): hemogramas, glucosa, orina, VIH, RPR, Hepatitis B
  - Campos: fecha, paciente, teléfono, doctor, examen, fecha resultado, monto, tipo pago, personal, estado entrega
- **XAMIRA** (laboratorio externo): urocultivos, CSV, B-HCG, perfiles hormonales, marcadores tumorales
  - Campos adicionales: fecha de pago a Xamira, estado de entrega
- Métodos de pago: Efectivo, Yape
- Resultados entregados por: WhatsApp, presencial, impreso
- Seguimiento de re-evaluaciones post-resultado

### Lo que tiene el backend:
- ✅ `LabOrder` con lifecycle: ordered → sample_taken → sent → result_received → delivered
- ✅ `LabResult` con resultado detallado (JSONB)
- ✅ Tipos: routine, cytology, pathology, hpv_test, fetal_dna, imaging
- ✅ Campo external_lab_name

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 6.1 | **Pago del examen** | ALTA | El ERP registra monto y método de pago por cada examen. El modelo LabOrder no tiene campos de pago (se debería vincular a CashMovement o Invoice). |
| 6.2 | **Fecha de pago al laboratorio externo** | ALTA | El ERP registra cuándo se le pagó a Xamira. Necesita concepto de "cuentas por pagar a proveedores". |
| 6.3 | **Responsable que recibe la muestra** | MEDIA | El ERP registra quién del personal recibió/procesó (Sandra, Fiorella, Yamilet). El backend no tiene `received_by`. |
| 6.4 | **Canal de entrega de resultado** | MEDIA | WhatsApp vs impreso vs presencial. No hay campo para esto. |
| 6.5 | **Vínculo con re-evaluación** | BAJA | Tras entregar resultado, se agenda re-evaluación. No hay workflow automático resultado → nueva cita. |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (70%)

---

## 7. PATOLOGÍA (Pestaña: PATO 26)

### Lo que hace el ERP:
- 44 biopsias registradas en 2026 con código secuencial (M26-01 a M26-44)
- Campos: código, nombre, edad, muestra, tipo, profesional, fecha recepción, fecha envío a proceso, lugar (Lima), celular, fecha resultado, fecha entrega, resultado, observación, monto, tipo pago
- Tipos de muestra: cérvix, vulva, mama, endometrio, tejido gástrico, pólipo, etc.
- Muestras enviadas a Lima para procesamiento
- Resultados en 5-7 días hábiles

### Lo que tiene el backend:
- ✅ `LabOrder` con type="pathology"
- ✅ `LabResult` con resultado detallado

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 7.1 | **Código secuencial de patología** | ALTA | El ERP usa M26-01, M26-02... (M=muestra, 26=año). El backend no genera códigos secuenciales por tipo. |
| 7.2 | **Tipo de muestra y tejido** | ALTA | No hay campo específico `sample_type` (cérvix, mama, endometrio...) ni `tissue_type`. |
| 7.3 | **Tracking de envío a Lima** | MEDIA | Fechas de recepción, envío a proceso, lugar de procesamiento. El lifecycle no distingue "enviado a proceso" de "enviado al lab externo". |
| 7.4 | **Número de casetes** | BAJA | El ERP registra cuántos casetes de muestra se enviaron. |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (55%)

---

## 8. CITOLOGÍA (Pestaña: CITO 26)

### Lo que hace el ERP:
- 123+ citologías (PAP) registradas en 2026
- Código secuencial: C26-01 a C26-123
- Campos: código, nombre, edad, tipo muestra (PAP cérvix, líquido pleural), clasificación (Paquete, Ginecológico, Particular), profesional, fechas, resultado (POSITIVO/NEGATIVO), método entrega
- Estado de pago: algunos marcados "DEBE"

### Lo que tiene el backend:
- ✅ `LabOrder` con type="cytology" y resultados en JSONB

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 8.1 | **Código secuencial de citología** | ALTA | Similar a patología, códigos C26-01, C26-02... |
| 8.2 | **Clasificación por origen** | MEDIA | Paquete vs Ginecológico vs Particular. Indica si viene de un paquete CPN, paquete gineco, o atención suelta. |
| 8.3 | **Estado de deuda** | MEDIA | Marcas de "DEBE" para pacientes que no han pagado. Necesita concepto de "cuenta por cobrar". |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (55%)

---

## 9. VACUNA GARDASIL (Pestaña: VACUNA GARDASIL)

### Lo que hace el ERP:
- Registro de vacunaciones con esquema de 3 dosis (0, 2, 6 meses)
- ~50 pacientes desde mayo 2025
- Campos: fecha, paciente, edad, dosis (1°, 2°, 3°), teléfono, responsable, costo (S/650), método de pago, fecha próxima dosis
- Control de stock (ingreso de vacunas con fecha)

### Lo que tiene el backend:
- ❌ **NO EXISTE** módulo de vacunación

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 9.1 | **Modelo de esquema de vacunación** | ALTA | Entidad para registrar: paciente, vacuna, dosis aplicada, fecha, próxima dosis, responsable. |
| 9.2 | **Recordatorio automático** | MEDIA | Notificar a pacientes cuando se acerque la fecha de su próxima dosis. |
| 9.3 | **Control de stock de vacunas** | MEDIA | Se puede cubrir con el módulo de inventario existente, pero necesita vinculación con la aplicación. |

### VEREDICTO: ❌ NO IMPLEMENTADO — Se puede modelar como LabOrder/Procedure o crear módulo específico

---

## 10. PAPILOCARE (Pestaña: PAPILOCARE)

### Lo que hace el ERP:
- 16 pacientes registradas
- Campos: fecha, paciente, edad, cantidad, responsable, monto (S/500), tipo de pago
- Control de stock (actualmente 0)

### Lo que tiene el backend:
- ⚠️ Se puede registrar como un servicio + movimiento de inventario, pero no hay workflow dedicado.

### VEREDICTO: ⚠️ CUBIERTO INDIRECTAMENTE — Usar Service + InventoryItem + CashMovement

---

## 11. T DE COBRE (Pestaña: T DE COBRE)

### Lo que hace el ERP:
- 22 colocaciones registradas
- Tipos: Mini T (S/280), T de Plata (S/360), T de Cobre Clásico (S/220), Coperflex Mini
- Campos: fecha, paciente, tipo, pago, método de pago, responsable
- Control de stock por tipo

### Lo que tiene el backend:
- ⚠️ Similar a Papilocare — se puede modelar como procedimiento + inventario.

### VEREDICTO: ⚠️ CUBIERTO INDIRECTAMENTE — Necesita seed de servicios con variantes

---

## 12. TEST PVH (Pestaña: TEST-PVH)

### Lo que hace el ERP:
- Registro de tests de detección molecular de VPH
- Similar a laboratorio externo

### Lo que tiene el backend:
- ✅ `LabOrder` con type="hpv_test" — ya soportado

### VEREDICTO: ✅ CUBIERTO (90%)

---

## 13. ADN FETAL (Pestaña: ADN FETAL)

### Lo que hace el ERP:
- Tests de ADN fetal (S/1,710)
- Campos: fecha muestra, paciente, doctor, tipo examen, fecha resultado, monto, método pago, responsable, observaciones
- Resultados enviados a Portales y agendamiento posterior

### Lo que tiene el backend:
- ✅ `LabOrder` con type="fetal_dna" — ya soportado

### VEREDICTO: ✅ CUBIERTO (90%)

---

## 14. MISOPROSTOL (Pestaña: MISOPROSTOL)

### Lo que hace el ERP:
- 8 registros de administración (AMEU, colocación de T)
- Control de pastillas usadas por procedimiento
- Total acumulado: 25 pastillas

### Lo que tiene el backend:
- ⚠️ Se cubre con inventario (StockMovement con reason="patient_use"), pero no hay vínculo directo procedimiento → insumo consumido.

### GAPS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 14.1 | **Vínculo procedimiento → insumos** | MEDIA | Al realizar un AMEU, debería descontar automáticamente el misoprostol del inventario. |

### VEREDICTO: ⚠️ CUBIERTO INDIRECTAMENTE (60%)

---

## 15. PRECIOS DE BIOPSIAS (Pestaña: PREC. BIOP)

### Lo que hace el ERP:
- Tarifario de laboratorio de patología (convenio con Eddie Santamaría Bedoya)
- Categorías: citología, biopsias pequeñas (<1cm), medianas (>1cm), piezas grandes, inmunohistoquímica
- Precios de convenio vs precio al público

### Lo que tiene el backend:
- ⚠️ Se puede modelar como servicios con categoría "patología", pero no hay concepto de "precio de convenio vs precio público" (doble precio).

### GAPS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 15.1 | **Doble precio (convenio vs público)** | MEDIA | El modelo Service solo tiene `price`. Necesita `cost_price` (lo que paga la clínica al proveedor) y `sale_price`. |

### VEREDICTO: ⚠️ PARCIALMENTE CUBIERTO (40%)

---

## 16. ROL DEL PERSONAL ASISTENCIAL (Pestañas: ROL-OBS., ROL FEB PERSONAL)

### Lo que hace el ERP:
- **ROL-OBS**: Turnos mensuales de obstetras CPN (Anali, Janeth, Sandy)
  - Turnos M (mañana), T (tarde), M/T (todo el día)
- **ROL FEB PERSONAL**: Turnos de TODO el personal asistencial
  - Recepcionistas, asistentes, laboratorio por sede
  - Distribución P (Portales) vs H (Huallayco)
  - Horarios: 8:00-14:00 y 14:00-20:00

### Lo que tiene el backend:
- ✅ `DoctorSchedule` para médicos
- ✅ `StaffScheduleOverride` para excepciones

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 16.1 | **Schedules para NO-médicos** | ALTA | El modelo es `DoctorSchedule`, pero el personal asistencial (recepcionistas, obstetras, lab) también necesita turnos. Debería ser `StaffSchedule`. |
| 16.2 | **Asignación de sede por turno** | ALTA | El personal rota entre sedes (P y H). Necesita campo `clinic_id` en el schedule diario. |
| 16.3 | **Rol de Obstetra** | MEDIA | No existe el rol "OBSTETRA" en el RBAC. Actualmente solo: SUPER_ADMIN, ORG_ADMIN, CLINIC_ADMIN, DOCTOR, RECEPTIONIST. |

### VEREDICTO: ⚠️ PARCIALMENTE CUBIERTO (40%)

---

## 17. CAJA / PAGOS (Pestaña: implícito en todo el ERP)

### Lo que hace el ERP:
- Cada pestaña registra: monto, método de pago (Efectivo, Yape, Tarjeta), responsable del cobro
- Adelantos parciales
- Estados de deuda ("DEBE")
- Pagos fraccionados por cuotas (CPN)

### Lo que tiene el backend:
- ✅ `CashSession`: apertura/cierre de caja
- ✅ `CashMovement`: ingresos/egresos con categoría y método de pago
- ✅ Métodos: cash, card, transfer, yape_plin
- ✅ Vinculación a invoice y patient

### GAPS IDENTIFICADOS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 17.1 | **Pagos parciales / cuotas** | CRÍTICA | No hay modelo de "plan de pagos" ni "cuota". El CPN se paga en cuotas y el ERP lo trackea. |
| 17.2 | **Cuentas por cobrar** | ALTA | Pacientes con deudas pendientes. No hay reporte ni entidad para esto. |
| 17.3 | **Cuentas por pagar a proveedores** | ALTA | Pagos a Xamira (lab externo), Eddie (patología). No hay modelo de cuentas por pagar. |
| 17.4 | **Conciliación Yape/transferencias** | MEDIA | El ERP distingue entre Yape y efectivo. El backend tiene `yape_plin` pero no hay conciliación bancaria. |

### VEREDICTO: ✅ PARCIALMENTE CUBIERTO (60%)

---

## 18. FACTURACIÓN SUNAT

### Lo que tiene el backend:
- ✅ `Invoice` + `InvoiceItem` completo
- ✅ Integración NubeFact
- ✅ Boleta, factura, nota de crédito/débito
- ✅ Serie, correlativo, IGV

### Lo que hace el ERP:
- ❌ NO tiene facturación — todo es manual (efectivo y Yape sin comprobante formal en el spreadsheet)

### VEREDICTO: ✅ EL BACKEND SUPERA AL ERP — Ventaja competitiva

---

## 19. NOTIFICACIONES / RECORDATORIOS

### Lo que hace el ERP:
- Llamadas telefónicas y WhatsApp manuales
- Resultados enviados por WhatsApp
- Confirmaciones de cita por llamada
- Recordatorios de próxima dosis de vacuna

### Lo que tiene el backend:
- ✅ SMS via Twilio
- ❌ No hay integración con WhatsApp

### GAPS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 19.1 | **Integración WhatsApp Business API** | ALTA | El canal principal de comunicación del CEM es WhatsApp, no SMS. |
| 19.2 | **Envío automático de resultados** | MEDIA | Al cambiar estado de LabOrder a "delivered", enviar resultado por WhatsApp. |
| 19.3 | **Recordatorios automáticos de citas** | MEDIA | Día anterior o mañana del día. |

### VEREDICTO: ⚠️ PARCIALMENTE CUBIERTO (30%)

---

## 20. REPORTES

### Lo que el negocio necesita (deducido del ERP):
- Ingresos por día/semana/mes por sede
- Producción por médico (servicios realizados + comisiones)
- Pacientes CPN activas y estado de pagos
- Stock de insumos (vacunas, Papilocare, T de cobre, Misoprostol)
- Biopsias/citologías pendientes y entregadas
- Cuentas por cobrar y por pagar

### Lo que tiene el backend:
- ✅ `report_service.py`: ingresos por período, por doctor, por servicio
- ✅ Estadísticas de pacientes y citas

### GAPS:

| # | Gap | Prioridad | Detalle |
|---|-----|-----------|---------|
| 20.1 | **Reporte de producción médica + comisiones** | ALTA | Cuántos servicios realizó cada médico y cuánto se le debe. |
| 20.2 | **Reporte de CPN activos** | ALTA | Estado de cada paciente CPN: pagos, controles realizados, próximo control. |
| 20.3 | **Reporte de laboratorio** | MEDIA | Pendientes, entregados, pagados a proveedor. |
| 20.4 | **Dashboard por sede** | MEDIA | Comparativa de ingresos y atenciones entre Huallayco y Portales. |

### VEREDICTO: ⚠️ PARCIALMENTE CUBIERTO (45%)

---

## 21. BOOKING PÚBLICO / RESERVAS ONLINE

### Lo que tiene el backend:
- ✅ Sistema completo de booking público sin autenticación
- ✅ Slug por clínica, listado de doctores y servicios, disponibilidad, reserva

### Lo que hace el ERP:
- ❌ No tiene — las citas se agendan por teléfono/WhatsApp

### VEREDICTO: ✅ EL BACKEND SUPERA AL ERP — Ventaja competitiva

---

## 22. FUNCIONALIDADES QUE EL BACKEND TIENE Y EL ERP NO

| Funcionalidad | Módulo Backend | Valor Agregado |
|---------------|---------------|----------------|
| Historia Clínica Electrónica (HCE) | MedicalRecord | Cumple NTS 139-MINSA, immutable, firmada digitalmente |
| Odontograma | DentalChart | Notación FDI, historial por diente |
| Oftalmología | OphthalmicExam | Refracción, PIO, agudeza visual |
| CIE-10 | CIE10Code | Catálogo completo de diagnósticos OMS |
| Facturación electrónica SUNAT | Invoice + NubeFact | Boletas, facturas, notas de crédito |
| Autenticación MFA | User (TOTP) | Seguridad de doble factor |
| Booking público online | Public routes | Reserva 24/7 sin llamar |
| Sincronización offline | SyncQueue | Funciona sin internet |
| Auditoría legal | AuditLog | 10 años de retención (Ley 30024) |
| Encriptación de datos personales | Fernet | Cumple protección de datos |
| Validación RENIEC | reniec_service | DNI/RUC automático |
| Multi-tenancy con RLS | PostgreSQL RLS | Aislamiento total de datos |

---

## RESUMEN DE PRIORIDADES

### 🔴 CRÍTICO (Bloquea operación diaria)

| # | Módulo/Feature | Esfuerzo Estimado |
|---|---------------|-------------------|
| 1 | **Modelo de Paquetes CPN** (entidad Paquete con servicios incluidos, cuotas, cronograma) | 3-5 días |
| 2 | **Pagos parciales / cuotas** (plan de pagos vinculado a paquete o servicio) | 2-3 días |
| 3 | **Módulo de comisiones médicas** (tabla de comisiones por servicio, liquidación) | 3-4 días |

### 🟠 ALTA PRIORIDAD (Necesario para paridad con ERP)

| # | Módulo/Feature | Esfuerzo Estimado |
|---|---------------|-------------------|
| 4 | Categorización de servicios + seed del tarifario CEM completo | 1-2 días |
| 5 | Campo `booked_by` en Appointment (responsable de agendamiento) | 0.5 días |
| 6 | Códigos secuenciales para patología (M26-XX) y citología (C26-XX) | 1 día |
| 7 | Integración WhatsApp Business API | 3-5 días |
| 8 | StaffSchedule generalizado (no solo doctores) + asignación por sede | 2-3 días |
| 9 | Cuentas por cobrar y por pagar | 2-3 días |
| 10 | Vista de rol mensual de médicos (endpoint calendario) | 1-2 días |
| 11 | Rol OBSTETRA en RBAC | 0.5 días |
| 12 | Doble precio en servicios (costo vs venta) | 0.5 días |
| 13 | Reporte de producción médica con comisiones | 1-2 días |

### 🟡 MEDIA PRIORIDAD (Mejora la operación)

| # | Módulo/Feature | Esfuerzo Estimado |
|---|---------------|-------------------|
| 14 | Módulo de vacunación (esquema de dosis + recordatorios) | 2-3 días |
| 15 | FUR y cálculo automático de semanas gestacionales | 1 día |
| 16 | Vínculo procedimiento → insumos consumidos (Misoprostol, etc.) | 1-2 días |
| 17 | Canal de entrega de resultado (WhatsApp/impreso/presencial) | 0.5 días |
| 18 | Dashboard comparativo por sede | 1-2 días |
| 19 | Recordatorios automáticos de citas y dosis | 1-2 días |

### 🟢 BAJA PRIORIDAD (Nice to have)

| # | Módulo/Feature | Esfuerzo Estimado |
|---|---------------|-------------------|
| 20 | Conteo de turnos mensuales por médico | 0.5 días |
| 21 | Número de casetes en patología | 0.5 días |
| 22 | Variantes de precio por servicio (gemelar, etc.) | 1 día |
| 23 | Conciliación bancaria Yape/transferencias | 2-3 días |

---

## PLAN DE ACCIÓN RECOMENDADO

### Fase 1: Paridad Operativa (2-3 semanas)
> Objetivo: Que el sistema pueda reemplazar al Google Sheets para la operación diaria.

1. Crear modelo `ServicePackage` + `PackageItem` + `PackagePayment` (Paquetes CPN)
2. Crear modelo `PaymentPlan` + `Installment` (pagos en cuotas)
3. Crear modelo `DoctorCommission` + `CommissionPayment` (comisiones médicas)
4. Agregar `category` a Service + seed completo del tarifario
5. Agregar `booked_by` a Appointment
6. Agregar `cost_price` a Service
7. Generalizar DoctorSchedule → StaffSchedule
8. Agregar rol OBSTETRA al RBAC

### Fase 2: Mejoras de Comunicación (1-2 semanas)
> Objetivo: Reemplazar las llamadas y WhatsApp manuales.

9. Integrar WhatsApp Business API (Meta Cloud API)
10. Automatizar envío de resultados de laboratorio
11. Recordatorios de citas (24h antes)
12. Recordatorios de próxima dosis de vacuna

### Fase 3: Reportes y Analytics (1-2 semanas)
> Objetivo: Dar visibilidad gerencial que el Google Sheets no puede dar.

13. Dashboard de producción médica + comisiones
14. Reporte de CPN activos con estado de pagos
15. Dashboard comparativo entre sedes
16. Cuentas por cobrar y por pagar

### Fase 4: Módulos Especializados (2-3 semanas)
> Objetivo: Cubrir el 100% de funcionalidad del ERP.

17. Módulo de vacunación con esquema de dosis
18. Códigos secuenciales lab (patología M-XX, citología C-XX)
19. FUR + cálculo de semanas gestacionales
20. Vínculo procedimiento → insumos

---

## CONCLUSIÓN

El backend actual es **técnicamente superior** al Google Sheets en arquitectura, seguridad y escalabilidad. Sin embargo, le faltan **funcionalidades de negocio críticas** que el CEM usa diariamente:

- **Paquetes CPN con cuotas** — el core del negocio obstétrico
- **Comisiones médicas** — cómo se paga a los doctores
- **Pagos parciales** — cómo pagan los pacientes

Estas 3 carencias representan el **60% del gap** entre el sistema actual y la operación real. Una vez resueltas, junto con la carga del tarifario completo, el sistema estaría listo para reemplazar el Google Sheets y ofrecer ventajas significativas como facturación SUNAT, historia clínica electrónica, y booking online.

**Esfuerzo total estimado para paridad completa: 6-10 semanas de desarrollo.**
