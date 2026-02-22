# SaaS de Gestión para Clínicas Especializadas — Plan de Hitos

> Plan de desarrollo del MVP organizado en **6 hitos (12 sprints de 2 semanas = 24 semanas)**.  
> Cada hito incluye tareas separadas por rol: **Backend**, **Frontend**, **Diseñador**, **DevOps/Infra** y **QA/Testing**.

---

## Tabla de Contenidos

- [Resumen del Stack](#resumen-del-stack)
- [Hito 1 — Fundación: Auth + Multi-Tenant + CRUD Pacientes (Semanas 1-4)](#hito-1--fundación-auth--multi-tenant--crud-pacientes-semanas-1-4)
- [Hito 2 — Calendario de Citas + Reserva Online (Semanas 5-8)](#hito-2--calendario-de-citas--reserva-online-semanas-5-8)
- [Hito 3 — Historia Clínica Electrónica + Especialidades (Semanas 9-12)](#hito-3--historia-clínica-electrónica--especialidades-semanas-9-12)
- [Hito 4 — Facturación SUNAT + WhatsApp Reminders (Semanas 13-16)](#hito-4--facturación-sunat--whatsapp-reminders-semanas-13-16)
- [Hito 5 — Offline-First PWA + Sincronización (Semanas 17-20)](#hito-5--offline-first-pwa--sincronización-semanas-17-20)
- [Hito 6 — Testing, QA, Polish + Preparación Beta (Semanas 21-24)](#hito-6--testing-qa-polish--preparación-beta-semanas-21-24)
- [Tareas Transversales (Todo el proyecto)](#tareas-transversales-todo-el-proyecto)
- [Próximos Pasos Inmediatos (Pre-Desarrollo)](#próximos-pasos-inmediatos-pre-desarrollo)

---

## Resumen del Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Frontend | Next.js 14+ (App Router) | 14.2+ |
| UI Components | shadcn/ui + Tailwind CSS | Latest |
| Backend API | FastAPI (Python 3.12+) | 0.110+ |
| ORM | SQLAlchemy 2.0 + Alembic | 2.0+ |
| Validación | Pydantic v2 | 2.6+ |
| Auth | FastAPI + JWT (PyJWT) RS256 | Custom |
| Base de datos | PostgreSQL 16 | 16+ |
| Cache | Redis (Upstash) | 7+ |
| Tareas async | Celery + Redis broker | 5.3+ |
| Offline/PWA | Service Workers + IndexedDB | Web API |
| Testing | Pytest + Playwright | Latest |

---

## Hito 1 — Fundación: Auth + Multi-Tenant + CRUD Pacientes (Semanas 1-4)

### Backend (FastAPI)

- [ ] **Scaffolding del proyecto FastAPI**
  - [ ] Crear estructura de carpetas (`app/`, `models/`, `schemas/`, `api/`, `services/`, `tasks/`, `core/`)
  - [ ] Configurar `main.py` con CORS middleware y routers
  - [ ] Crear `config.py` con Pydantic `BaseSettings` (variables de entorno)
  - [ ] Configurar `database.py` con AsyncSession, engine y setup de RLS
  - [ ] Crear `Dockerfile` y `docker-compose.yml` (FastAPI + PostgreSQL + Redis)
  - [ ] Configurar `requirements.txt` con todas las dependencias base

- [ ] **Autenticación y Autorización**
  - [ ] Implementar generación/verificación de JWT RS256 (`auth/jwt.py`)
  - [ ] Crear endpoints `POST /api/v1/auth/login` y `POST /api/v1/auth/register`
  - [ ] Implementar refresh tokens (7 días de duración)
  - [ ] Crear dependency `get_current_user` para inyección en rutas (`auth/dependencies.py`)
  - [ ] Implementar sistema RBAC con roles: `super_admin`, `clinic_admin`, `doctor`, `receptionist` (`auth/rbac.py`)
  - [ ] Crear decorator/dependency `require_role(...)` para proteger rutas
  - [ ] Implementar MFA con TOTP (obligatorio para doctors/admins)
  - [ ] Implementar hashing seguro de contraseñas (`core/security.py`)

- [ ] **Multi-Tenancy con RLS**
  - [ ] Crear modelo SQLAlchemy `Clinic` con campos: `id`, `name`, `ruc`, `address`, `phone`, `specialty_type`, `timezone`, `settings (JSONB)`
  - [ ] Habilitar Row-Level Security en PostgreSQL para todas las tablas
  - [ ] Crear políticas RLS: `USING (clinic_id = current_setting('app.clinic_id')::uuid)`
  - [ ] Implementar middleware/dependency que setee `SET LOCAL app.clinic_id` en cada request
  - [ ] Validar RUC con formato SUNAT

- [ ] **Modelo de Datos Base**
  - [ ] Crear modelo `User` (`id`, `clinic_id`, `email`, `hashed_password`, `role`, `cmp_number`, `specialty`, `is_mfa_enabled`)
  - [ ] Crear modelo `Patient` (`id`, `clinic_id`, `dni`, `first_name`, `last_name`, `birth_date`, `phone`, `email`, `blood_type`, `allergies (JSONB)`)
  - [ ] Crear modelo `AuditLog` (`id`, `clinic_id`, `user_id`, `entity`, `entity_id`, `action`, `old_data`, `new_data`, `ip`, `user_agent`, `created_at`) — INSERT-only, sin permisos UPDATE/DELETE
  - [ ] Configurar Alembic para migraciones
  - [ ] Crear migración inicial con todas las tablas base
  - [ ] Crear índice en `patients.dni` para búsqueda rápida

- [ ] **CRUD Pacientes API**
  - [ ] Crear schemas Pydantic: `PatientCreate`, `PatientUpdate`, `PatientResponse`
  - [ ] Implementar `GET /api/v1/patients` (listado paginado con filtros)
  - [ ] Implementar `GET /api/v1/patients/{id}` (detalle)
  - [ ] Implementar `POST /api/v1/patients` (crear paciente)
  - [ ] Implementar `PUT /api/v1/patients/{id}` (actualizar)
  - [ ] Implementar búsqueda por DNI: `GET /api/v1/patients/search?dni=...`
  - [ ] Registrar todas las operaciones en `audit_log`

- [ ] **Cifrado de PII**
  - [ ] Implementar cifrado Fernet para campos sensibles (DNI, teléfono, email) con `cryptography` lib
  - [ ] Crear helpers de encrypt/decrypt en `core/security.py`

- [ ] **Custom Exceptions**
  - [ ] Crear `core/exceptions.py` con excepciones HTTP personalizadas
  - [ ] Configurar exception handlers globales en `main.py`

### Frontend (Next.js)

- [ ] **Scaffolding del proyecto**
  - [ ] Inicializar Next.js 14+ con App Router y TypeScript
  - [ ] Configurar Tailwind CSS + shadcn/ui
  - [ ] Crear estructura de carpetas: `(auth)/`, `(dashboard)/`, `components/`, `lib/`, `hooks/`
  - [ ] Configurar `next.config.js`
  - [ ] Crear `lib/api-client.ts` — fetch wrapper con interceptors para JWT

- [ ] **Módulo de Autenticación**
  - [ ] Página de Login (`(auth)/login`)
  - [ ] Página de Registro de clínica (`(auth)/register`)
  - [ ] Flujo de MFA/TOTP para doctors y admins
  - [ ] Implementar `lib/auth.ts` — almacenamiento de JWT + refresh automático
  - [ ] Implementar protección de rutas (redirect a login si no autenticado)
  - [ ] Crear layout autenticado `(dashboard)/layout.tsx` con sidebar y header

- [ ] **Módulo de Pacientes**
  - [ ] Listado de pacientes con tabla paginada, búsqueda y filtros
  - [ ] Vista de perfil/ficha de paciente
  - [ ] Formulario de creación de paciente
  - [ ] Formulario de edición de paciente
  - [ ] Búsqueda rápida por DNI

- [ ] **Componentes UI Base**
  - [ ] Instalar y configurar componentes shadcn/ui necesarios (Button, Input, Table, Dialog, Form, Card, etc.)
  - [ ] Crear componente de Sidebar/Navegación principal
  - [ ] Crear componente de Header con info de usuario y clínica
  - [ ] Crear componentes de formulario reutilizables

### Diseñador (UI/UX)

- [ ] **Sistema de diseño base**
  - [ ] Definir paleta de colores (primary, secondary, accents, semánticos para estados médicos)
  - [ ] Definir tipografía (headings, body, monospace para códigos médicos)
  - [ ] Definir espaciado, bordes y sombras
  - [ ] Crear tokens de diseño compatibles con Tailwind CSS

- [ ] **Diseño de pantallas Hito 1**
  - [ ] Diseñar pantalla de Login (con opción MFA)
  - [ ] Diseñar pantalla de Registro de clínica (onboarding)
  - [ ] Diseñar layout principal del dashboard (sidebar + header + content area)
  - [ ] Diseñar listado de pacientes (tabla con filtros, búsqueda, paginación)
  - [ ] Diseñar ficha/perfil de paciente (datos personales, tabs para secciones futuras)
  - [ ] Diseñar formulario de creación/edición de paciente
  - [ ] Diseñar estados vacíos, loading y error

- [ ] **Prototipo en Figma**
  - [ ] Usar kit Preclinic como base de diseño
  - [ ] Crear componentes reutilizables en Figma (botones, inputs, cards, tables)
  - [ ] Diseñar versión mobile-first (PWA)
  - [ ] Entregar assets exportables y especificaciones

### DevOps / Infraestructura

- [ ] Crear repositorios en GitHub (backend + frontend o monorepo con Turborepo)
- [ ] Configurar entorno Docker local: `docker-compose` con FastAPI + PostgreSQL 16 + Redis
- [ ] Configurar CI/CD básico (GitHub Actions): linting + tests en cada PR
- [ ] Configurar deploy de staging para Backend en Railway.app (o Render.com como alternativa)
- [ ] Configurar deploy de staging para Frontend en Vercel
- [ ] Configurar PostgreSQL con RLS habilitado en staging
- [ ] Configurar variables de entorno y secretos

### QA / Testing

- [ ] Configurar Pytest para el backend con fixtures base (client, db session, test user)
- [ ] Tests unitarios para JWT (generación, verificación, expiración)
- [ ] Tests unitarios para RBAC (permisos por rol)
- [ ] Tests de integración para CRUD de pacientes
- [ ] Tests de integración para RLS (verificar aislamiento entre clínicas)
- [ ] Tests de validación de datos (DNI, RUC, campos obligatorios)

---

## Hito 2 — Calendario de Citas + Reserva Online (Semanas 5-8)

### Backend (FastAPI)

- [ ] **Modelo de Citas**
  - [ ] Crear modelo `Appointment` (`id`, `clinic_id`, `patient_id`, `doctor_id`, `start_time`, `end_time`, `status`, `service_type`, `notes`)
  - [ ] Implementar state machine de estados: `scheduled` → `confirmed` → `in_progress` → `completed` / `no_show` / `cancelled`
  - [ ] Crear migración Alembic para tabla `appointments`
  - [ ] Crear índices para consultas por fecha, doctor y estado

- [ ] **API de Citas**
  - [ ] Crear schemas Pydantic: `AppointmentCreate`, `AppointmentUpdate`, `AppointmentResponse`
  - [ ] Implementar `GET /api/v1/appointments` (listado con filtros: fecha, doctor, estado)
  - [ ] Implementar `GET /api/v1/appointments/{id}` (detalle)
  - [ ] Implementar `POST /api/v1/appointments` (crear cita)
  - [ ] Implementar `PUT /api/v1/appointments/{id}` (actualizar)
  - [ ] Implementar `PATCH /api/v1/appointments/{id}/status` (cambiar estado)
  - [ ] Implementar `GET /api/v1/appointments/availability` (consulta de disponibilidad en tiempo real)
  - [ ] Validar solapamiento de citas (mismo doctor, misma hora)
  - [ ] Registrar cambios de estado en `audit_log`

- [ ] **Disponibilidad y Horarios**
  - [ ] Crear modelo/config para horarios de atención por doctor
  - [ ] Implementar lógica de slots disponibles
  - [ ] Endpoint público para reserva online (sin autenticación, con token de clínica)

### Frontend (Next.js)

- [ ] **Calendario Interactivo**
  - [ ] Integrar `react-big-calendar` (o similar)
  - [ ] Vistas: día, semana, mes
  - [ ] Código de colores por estado de cita
  - [ ] Drag & drop para reprogramar citas
  - [ ] Modal de creación rápida de cita desde el calendario

- [ ] **Gestión de Citas**
  - [ ] Formulario completo de nueva cita (selección de paciente, doctor, servicio, horario)
  - [ ] Vista de detalle de cita con acciones (confirmar, iniciar, completar, cancelar, no-show)
  - [ ] Vista de agenda diaria del doctor
  - [ ] Filtros por doctor, estado, tipo de servicio

- [ ] **Reserva Online (Público)**
  - [ ] Página pública de reserva con link compartible
  - [ ] Selección de especialidad/servicio → doctor → horario disponible
  - [ ] Formulario de datos del paciente (nuevo o existente por DNI)
  - [ ] Confirmación de reserva

### Diseñador (UI/UX)

- [ ] Diseñar calendario interactivo (vistas día/semana/mes)
- [ ] Diseñar sistema de colores para estados de cita
- [ ] Diseñar modal de creación rápida de cita
- [ ] Diseñar formulario completo de nueva cita
- [ ] Diseñar vista de agenda diaria del doctor
- [ ] Diseñar página pública de reserva online (branding de la clínica)
- [ ] Diseñar flujo de reserva paso a paso (mobile-first)
- [ ] Diseñar notificaciones y confirmaciones visuales de cambio de estado

### QA / Testing

- [ ] Tests de integración para API de citas (CRUD completo)
- [ ] Tests de la state machine de estados (transiciones válidas e inválidas)
- [ ] Tests de validación de solapamiento de horarios
- [ ] Tests de disponibilidad (slots correctos)
- [ ] Tests de endpoint público de reserva

---

## Hito 3 — Historia Clínica Electrónica + Especialidades (Semanas 9-12)

### Backend (FastAPI)

- [ ] **Modelo de Historia Clínica (HCE)**
  - [ ] Crear modelo `MedicalRecord` (`id`, `clinic_id`, `patient_id`, `doctor_id`, `record_type`, `cie10_codes (array)`, `content (JSONB)`, `specialty_data (JSONB)`, `signed_at`)
  - [ ] Configurar como INSERT-only (inmutable por normativa NTS 139)
  - [ ] Crear migración Alembic

- [ ] **API de Historia Clínica**
  - [ ] Crear schemas Pydantic con validación CIE-10 integrada
  - [ ] Implementar `POST /api/v1/records` (crear registro clínico)
  - [ ] Implementar `GET /api/v1/records?patient_id=...` (historial del paciente)
  - [ ] Implementar `GET /api/v1/records/{id}` (detalle)
  - [ ] Restricción: doctor solo accede a sus pacientes (RBAC + RLS)
  - [ ] Restricción: receptionist NO puede ver HCE

- [ ] **Servicio CIE-10**
  - [ ] Crear `services/cie10_service.py` con catálogo CIE-10
  - [ ] Implementar búsqueda/autocompletado de códigos CIE-10
  - [ ] Endpoint `GET /api/v1/cie10/search?q=...` para búsqueda por texto
  - [ ] (Futuro) Preparar estructura para ML con sentence-transformers

- [ ] **Especialidad: Odontología**
  - [ ] Crear modelo `DentalChart` (`id`, `record_id`, `tooth_number (FDI)`, `surfaces`, `condition`, `treatment`, `notes`)
  - [ ] API CRUD para odontograma con historial versionado
  - [ ] Endpoint para obtener estado actual completo del odontograma de un paciente

- [ ] **Especialidad: Obstetricia (Prenatal)**
  - [ ] Crear modelo `PrenatalVisit` (`id`, `record_id`, `gestational_week`, `weight`, `blood_pressure`, `uterine_height`, `fetal_hr`, `presentation`, `labs (JSONB)`)
  - [ ] API CRUD para fichas prenatales siguiendo estándar CLAP/SIP
  - [ ] Endpoint para obtener historial prenatal completo

- [ ] **Especialidad: Oftalmología**
  - [ ] Crear modelo `OphthalmicExam` (`id`, `record_id`, `eye (OD/OS)`, `visual_acuity`, `sphere`, `cylinder`, `axis`, `addition`, `iop`, `notes`)
  - [ ] API CRUD para fichas oftalmológicas
  - [ ] Endpoint para obtener historial de exámenes

- [ ] **Firma Digital**
  - [ ] Implementar campo `signed_at` como equivalente a firma digital del doctor
  - [ ] Una vez firmado, el registro no puede ser modificado

### Frontend (Next.js)

- [ ] **Motor HCE Dinámico**
  - [ ] Componente de creación de nota clínica con campos dinámicos según especialidad
  - [ ] Autocompletado de códigos CIE-10 en tiempo real
  - [ ] Historial clínico del paciente (timeline/lista cronológica)
  - [ ] Vista de detalle de registro clínico
  - [ ] Indicador de firma digital

- [ ] **Odontograma Interactivo**
  - [ ] Componente SVG interactivo del odontograma (32 dientes, sistema FDI)
  - [ ] Selección de superficies dentales (vestibular, lingual, mesial, distal, oclusal)
  - [ ] Código de colores por condición/tratamiento
  - [ ] Historial de tratamientos por diente
  - [ ] Vista de impresión del odontograma

- [ ] **Ficha Prenatal**
  - [ ] Formulario de control prenatal con todos los campos CLAP/SIP
  - [ ] Curvas de seguimiento (peso, altura uterina, presión arterial)
  - [ ] Resumen del embarazo con alertas

- [ ] **Ficha Oftalmológica**
  - [ ] Formulario de examen oftalmológico (refracción, PIO)
  - [ ] Vista comparativa OD vs OS
  - [ ] Historial de exámenes con evolución

### Diseñador (UI/UX)

- [ ] Diseñar flujo de creación de nota clínica (paso a paso o formulario completo)
- [ ] Diseñar timeline/historial clínico del paciente
- [ ] Diseñar odontograma SVG interactivo (dentición adulta e infantil)
- [ ] Diseñar paleta de colores para condiciones dentales
- [ ] Diseñar ficha prenatal digital (basada en formato CLAP/SIP)
- [ ] Diseñar gráficas de curvas prenatales
- [ ] Diseñar ficha oftalmológica digital
- [ ] Diseñar vista de impresión de HCE (para entrega legal al paciente)
- [ ] Diseñar iconografía médica especializada

### QA / Testing

- [ ] Tests de integración para API de registros médicos
- [ ] Tests de inmutabilidad (no se puede UPDATE/DELETE un registro firmado)
- [ ] Tests de autorización (doctor solo ve sus pacientes, receptionist no ve HCE)
- [ ] Tests de validación CIE-10
- [ ] Tests de API de odontograma
- [ ] Tests de API de fichas prenatales y oftalmológicas

---

## Hito 4 — Facturación SUNAT + WhatsApp Reminders (Semanas 13-16)

### Backend (FastAPI)

- [ ] **Modelo de Facturación**
  - [ ] Crear modelo `Invoice` (`id`, `clinic_id`, `patient_id`, `serie`, `correlativo`, `tipo_doc (F/B)`, `igv`, `total`, `sunat_status`, `nubefact_response (JSONB)`)
  - [ ] Campos SUNAT: serie, correlativo, tipo_comprobante, moneda, forma_pago
  - [ ] Crear migración Alembic

- [ ] **Integración NubeFact (SUNAT)**
  - [ ] Crear `services/sunat_service.py` con integración NubeFact API
  - [ ] Crear `tasks/sunat_tasks.py` — tarea Celery para emisión de comprobantes
  - [ ] Implementar `POST /api/v1/invoices` (crear y emitir factura/boleta)
  - [ ] Implementar `GET /api/v1/invoices` (listado con filtros)
  - [ ] Implementar `GET /api/v1/invoices/{id}` (detalle con estado SUNAT)
  - [ ] Manejar reintentos en caso de fallo de SUNAT
  - [ ] Implementar anulaciones
  - [ ] Cola offline: si no hay internet, encolar emisión para cuando reconecte

- [ ] **Integración WhatsApp (Meta Cloud API)**
  - [ ] Crear `services/whatsapp_service.py` con Meta WhatsApp Cloud API
  - [ ] Crear `tasks/whatsapp_tasks.py` — tarea Celery para envío de mensajes
  - [ ] Implementar recordatorios automáticos de cita (24h antes, 1h antes)
  - [ ] Implementar confirmación de cita por WhatsApp
  - [ ] Implementar notificación de factura/boleta emitida
  - [ ] Cron job para envío programado de recordatorios

- [ ] **Reportes Básicos**
  - [ ] Crear `tasks/reports_tasks.py` — generación asíncrona de reportes
  - [ ] Endpoint `GET /api/v1/reports/dashboard` — KPIs principales (citas del día, ingresos del mes, pacientes nuevos, tasa de no-show)
  - [ ] Endpoint `GET /api/v1/reports/revenue` — reporte de ingresos por período
  - [ ] Endpoint `GET /api/v1/reports/appointments` — estadísticas de citas

### Frontend (Next.js)

- [ ] **Módulo de Facturación**
  - [ ] Formulario de emisión de factura/boleta
  - [ ] Selección de paciente + servicios realizados
  - [ ] Cálculo automático de IGV y total
  - [ ] Listado de comprobantes con estado SUNAT (emitido, aceptado, rechazado)
  - [ ] Vista de detalle de comprobante con respuesta SUNAT
  - [ ] Opción de reintento para comprobantes fallidos
  - [ ] Descarga/impresión de comprobante en formato PDF

- [ ] **Configuración de Recordatorios**
  - [ ] Panel de configuración de mensajes WhatsApp
  - [ ] Activar/desactivar recordatorios automáticos
  - [ ] Configurar horarios y frecuencia de recordatorios
  - [ ] Historial de mensajes enviados

- [ ] **Dashboard de Reportes**
  - [ ] Dashboard con KPIs principales (cards con métricas)
  - [ ] Gráfico de ingresos por período
  - [ ] Gráfico de citas por estado
  - [ ] Indicadores de no-show
  - [ ] Filtros por rango de fechas

### Diseñador (UI/UX)

- [ ] Diseñar formulario de emisión de factura/boleta (UX simplificada)
- [ ] Diseñar listado de comprobantes con indicadores de estado SUNAT
- [ ] Diseñar vista de detalle de comprobante
- [ ] Diseñar formato de impresión de comprobante (ticket / A4)
- [ ] Diseñar panel de configuración de WhatsApp
- [ ] Diseñar dashboard de reportes con gráficos y KPIs
- [ ] Diseñar cards de métricas y componentes de gráficos

### DevOps / Infraestructura

- [ ] Crear cuenta sandbox en NubeFact para pruebas de facturación
- [ ] Registrar cuenta Meta Business para WhatsApp API
- [ ] Configurar Celery workers + Redis broker en staging
- [ ] Configurar cron jobs para recordatorios

### QA / Testing

- [ ] Tests de integración para API de facturación
- [ ] Tests de integración con NubeFact sandbox
- [ ] Tests de formato SUNAT (serie, correlativo, IGV)
- [ ] Tests de colas Celery (emisión, reintento, anulación)
- [ ] Tests de servicio WhatsApp (mocks)
- [ ] Tests de generación de reportes

---

## Hito 5 — Offline-First PWA + Sincronización (Semanas 17-20)

### Backend (FastAPI)

- [ ] **Endpoint de Sincronización**
  - [ ] Crear modelo `SyncQueue` (`id`, `clinic_id`, `device_id`, `operations (JSONB)`, `status`, `created_at`, `processed_at`)
  - [ ] Crear schemas: `SyncOperation`, `SyncBatch`, `SyncResponse`
  - [ ] Implementar `POST /api/v1/sync` — endpoint principal de sincronización
  - [ ] Recibir batch de operaciones (entity, action, local_id, data, timestamp)
  - [ ] Responder con: `applied` (operaciones exitosas), `conflicts` (conflictos), `updates` (cambios del servidor desde last_sync)

- [ ] **Resolución de Conflictos**
  - [ ] Crear `services/sync_service.py`
  - [ ] Implementar estrategia Last-Write-Wins basada en timestamp del cliente
  - [ ] Manejar mapeo `local_id` ↔ `server_id` para entidades creadas offline
  - [ ] Registros médicos: sin conflictos de UPDATE (son INSERT-only por normativa)
  - [ ] Background job para procesar colas de sync pesadas

- [ ] **Operaciones Offline Encoladas**
  - [ ] Encolar emisión SUNAT cuando se ejecuta en modo offline
  - [ ] Encolar envío de WhatsApp cuando se ejecuta en modo offline
  - [ ] Procesar cola automáticamente al detectar reconexión

### Frontend (Next.js)

- [ ] **Service Worker + PWA**
  - [ ] Crear `public/sw.js` — Service Worker con estrategia cache-first
  - [ ] Crear `public/manifest.json` — PWA manifest (nombre, icono, theme, display: standalone)
  - [ ] Registrar Service Worker en la app
  - [ ] Cache de assets estáticos y páginas del shell
  - [ ] Configurar Background Sync API

- [ ] **IndexedDB con Dexie.js**
  - [ ] Crear `lib/offline-db.ts` con clase `ClinicDB` (Dexie)
  - [ ] Tablas offline: `patients`, `appointments`, `records`, `syncQueue`
  - [ ] Índices optimizados para búsqueda offline (DNI, fecha, estado)
  - [ ] Cifrado de IndexedDB con Web Crypto API
  - [ ] Auto-borrado de datos locales al cerrar sesión

- [ ] **Sync Manager**
  - [ ] Crear `lib/sync-manager.ts` — cola de sincronización
  - [ ] Detectar estado online/offline automáticamente
  - [ ] Trigger de sync al reconectar
  - [ ] Sync manual desde la UI
  - [ ] Manejar respuesta del servidor: aplicar actualizaciones, resolver conflictos

- [ ] **Hooks y Componentes Offline**
  - [ ] Crear `hooks/useOffline.ts` — estado online/offline reactivo
  - [ ] Crear `hooks/useSync.ts` — estado de sincronización y trigger manual
  - [ ] Crear `hooks/usePatients.ts` (y similares) — queries con fallback a IndexedDB
  - [ ] Crear `components/offline/` — indicador de estado de conexión y sync
  - [ ] Crear banner de "modo offline" visible en toda la app
  - [ ] Indicador de operaciones pendientes de sincronizar

- [ ] **Funcionalidades que operan offline**
  - [ ] Consultar pacientes (lectura desde IndexedDB)
  - [ ] Crear/editar citas
  - [ ] Registrar notas clínicas
  - [ ] Ver odontograma
  - [ ] Llenar fichas obstétricas
  - [ ] Generar recibos preliminares
  - [ ] Ver agenda del día

### Diseñador (UI/UX)

- [ ] Diseñar indicador visual de estado de conexión (online/offline/sincronizando)
- [ ] Diseñar banner de modo offline (no intrusivo pero claro)
- [ ] Diseñar indicador de operaciones pendientes de sync
- [ ] Diseñar flujo de resolución de conflictos (si se requiere intervención del usuario)
- [ ] Diseñar pantalla de instalación PWA (prompt "Agregar a pantalla de inicio")
- [ ] Diseñar splash screen de la PWA
- [ ] Diseñar iconos de la PWA (192x192, 512x512, maskable)

### QA / Testing

- [ ] Tests del endpoint de sincronización (batch de operaciones)
- [ ] Tests de resolución de conflictos (last-write-wins)
- [ ] Tests de mapeo local_id ↔ server_id
- [ ] Tests de cola de operaciones offline
- [ ] Tests E2E de flujo offline → online → sync
- [ ] Auditoría PWA con Lighthouse (target: score > 90)

---

## Hito 6 — Testing, QA, Polish + Preparación Beta (Semanas 21-24)

### Backend (FastAPI)

- [ ] **Suite de Tests Completa**
  - [ ] Completar cobertura de tests unitarios (objetivo: > 80%)
  - [ ] Tests de integración para todos los endpoints
  - [ ] Tests de seguridad: RLS, RBAC, JWT expirado, refresh tokens
  - [ ] Tests de edge cases: datos corruptos, payloads malformados
  - [ ] Tests de concurrencia: sync simultáneo desde múltiples dispositivos

- [ ] **Load Testing**
  - [ ] Configurar Locust o k6 para pruebas de carga
  - [ ] Simular carga de 100 clínicas concurrentes
  - [ ] Identificar y optimizar cuellos de botella
  - [ ] Verificar tiempos de respuesta bajo carga (< 200ms p95)

- [ ] **Security Audit**
  - [ ] Revisar todas las rutas por vulnerabilidades (SQL injection, XSS, CSRF)
  - [ ] Verificar cifrado de PII en reposo
  - [ ] Auditar logs de audit_trail (completitud)
  - [ ] Verificar cumplimiento Ley 29733, NTS 139, RENHICE
  - [ ] Verificar aislamiento RLS bajo stress

- [ ] **Documentación API**
  - [ ] Verificar que OpenAPI/Swagger en `/docs` esté completo y correcto
  - [ ] Documentar flujos de autenticación
  - [ ] Documentar endpoint de sincronización con ejemplos
  - [ ] Documentar errores y códigos de respuesta

- [ ] **Rate Limiting y Protección**
  - [ ] Implementar rate limiting con Redis (por IP y por tenant)
  - [ ] Configurar protección contra brute force en login
  - [ ] Cache de sesiones con Redis

### Frontend (Next.js)

- [ ] **Tests E2E con Playwright**
  - [ ] Tests E2E de flujo de login completo
  - [ ] Tests E2E de CRUD de pacientes
  - [ ] Tests E2E de creación de cita
  - [ ] Tests E2E de creación de nota clínica
  - [ ] Tests E2E de emisión de factura
  - [ ] Tests E2E de flujo offline → online

- [ ] **Auditoría PWA (Lighthouse)**
  - [ ] Performance score > 90
  - [ ] Accessibility score > 90
  - [ ] Best Practices score > 90
  - [ ] SEO score > 90
  - [ ] PWA score: todas las verificaciones pasadas

- [ ] **Responsive y Mobile**
  - [ ] Verificar y ajustar todas las pantallas en mobile (360px - 768px)
  - [ ] Verificar en tablets (768px - 1024px)
  - [ ] Verificar en desktop (1024px+)
  - [ ] Optimizar touch targets para mobile

- [ ] **Onboarding**
  - [ ] Flujo de primera configuración de clínica (wizard)
  - [ ] Tour guiado de funcionalidades principales
  - [ ] Carga de datos iniciales (catálogo CIE-10, configuración por defecto)
  - [ ] Invitación de usuarios/equipo

- [ ] **Polish y UX**
  - [ ] Optimizar tiempos de carga (lazy loading, code splitting)
  - [ ] Mejorar feedback visual (loading states, toasts, transiciones)
  - [ ] Verificar accesibilidad (WCAG 2.1 AA)
  - [ ] Internacionalización (español por defecto, preparar estructura para otros idiomas)

### Diseñador (UI/UX)

- [ ] Diseñar flujo de onboarding/wizard de configuración inicial
- [ ] Diseñar tour guiado de funcionalidades
- [ ] Revisar consistencia visual en todas las pantallas
- [ ] Ajustar diseño responsive en pantallas que lo requieran
- [ ] Diseñar pantalla de error 404 y 500
- [ ] Diseñar email templates (bienvenida, invitación, recuperación de contraseña)
- [ ] Preparar materiales de branding para beta (landing page, email de invitación)

### DevOps / Infraestructura

- [ ] Configurar entorno de producción (Railway / Render / AWS ECS)
- [ ] Configurar PostgreSQL de producción con RDS encryption at rest (AES-256)
- [ ] Configurar S3 con Server-Side Encryption (AWS KMS) para archivos
- [ ] Configurar HSTS y TLS 1.2+
- [ ] Configurar backups automáticos de PostgreSQL (cifrados)
- [ ] Configurar monitoreo y alertas (errores, latencia, uptime)
- [ ] Configurar logging centralizado
- [ ] Preparar runbook de incidentes (notificación ANPDP en 48h)
- [ ] Dominio y certificados SSL para producción

### QA / Testing

- [ ] Ejecución completa de suite de tests (backend + frontend)
- [ ] Testing manual de todos los flujos críticos
- [ ] Testing de seguridad (penetration testing básico)
- [ ] Testing de rendimiento bajo carga
- [ ] Testing cross-browser (Chrome, Firefox, Safari, Edge)
- [ ] Testing en dispositivos reales (Android + iOS)
- [ ] Verificar funcionalidad offline en condiciones reales (simulación de Huánuco)
- [ ] Smoke test de producción pre-lanzamiento

---

## Tareas Transversales (Todo el proyecto)

### Backend

- [ ] Mantener migraciones Alembic actualizadas en cada hito
- [ ] Documentar todos los endpoints en OpenAPI/Swagger
- [ ] Mantener `audit_log` registrando todas las operaciones sensibles
- [ ] Code reviews en cada PR
- [ ] Mantener `requirements.txt` actualizado

### Frontend

- [ ] Mantener componentes shadcn/ui actualizados
- [ ] Mantener consistencia visual con el sistema de diseño
- [ ] Optimizar bundle size en cada release
- [ ] Code reviews en cada PR

### Diseñador

- [ ] Mantener librería de componentes Figma actualizada
- [ ] Documentar decisiones de diseño
- [ ] Realizar tests de usabilidad cuando sea posible
- [ ] Iterar diseños basándose en feedback del equipo

### DevOps

- [ ] Mantener pipelines CI/CD funcionando
- [ ] Monitorear costos de infraestructura
- [ ] Actualizar dependencias de seguridad

---

## Próximos Pasos Inmediatos (Pre-Desarrollo)

1. **Repositorios**: Crear repos en GitHub (`backend/` y `frontend/` o monorepo con Turborepo)
2. **Docker Local**: Configurar `docker-compose` con FastAPI + PostgreSQL 16 + Redis
3. **Freelancers**: Publicar brief de contratación en Workana/Torre.ai para freelancer Python/FastAPI
4. **Diseño**: Iniciar diseño en Figma usando el kit Preclinic como base
5. **NubeFact**: Crear cuenta sandbox para pruebas de facturación SUNAT
6. **WhatsApp**: Registrar cuenta Meta Business para WhatsApp API

---

## Normativa Legal Aplicable

| Normativa | Área | Descripción |
|---|---|---|
| Ley 29733 | Protección de datos | Cifrado de PII en tránsito y reposo |
| NTS 139-MINSA | Historia clínica | Registros médicos inmutables, acceso controlado |
| RENHICE | Autenticación | MFA obligatorio para personal médico |
| Ley 30024 | Audit trail | Registros de auditoría inmutables, retención 10 años |
| DS 016-2024-JUS | Cifrado | Campos PII cifrados con Fernet |
| DS 016-2024 Art. 28 | Incidentes | Notificación a ANPDP en 48 horas |

---

> **Equipo sugerido**: 1 founder/PM + 1 Backend Developer (Python/FastAPI) + 1 Frontend Developer (Next.js/React) + 1 Diseñador UI/UX (Figma) + QA/Testing compartido  
> **Duración estimada del MVP**: 24 semanas (6 meses)  
> **Metodología**: Sprints de 2 semanas con demos al final de cada hito
