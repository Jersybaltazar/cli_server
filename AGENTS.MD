# AGENTS.MD — SaaS de Gestión para Clínicas Especializadas (Backend)

> Guía técnica completa para agentes de IA y desarrolladores que trabajen en este repositorio.

---

## 1. Visión General del Proyecto

**SaaS Clínicas** es una plataforma multi-tenant de gestión clínica especializada construida con **FastAPI + PostgreSQL**, diseñada para clínicas en Perú. El sistema soporta múltiples especialidades médicas (odontología, obstetricia, oftalmología), facturación electrónica SUNAT, recordatorios por WhatsApp, y funcionalidad **offline-first** vía PWA.

### Características clave
- **Multi-tenancy** con Row-Level Security (RLS) en PostgreSQL — aislamiento de datos a nivel DB
- **Autenticación JWT RS256** con access/refresh tokens y MFA (TOTP)
- **RBAC** granular con 4 roles: `super_admin`, `clinic_admin`, `doctor`, `receptionist`
- **Cifrado de PII** con Fernet (DNI, teléfono, email)
- **Historia Clínica Electrónica** inmutable (INSERT-only) según NTS 139-MINSA
- **Especialidades**: Odontología (odontograma FDI), Obstetricia (CLAP/SIP), Oftalmología
- **Facturación SUNAT** vía NubeFact API
- **Sincronización offline** con resolución de conflictos last-write-wins
- **Tareas asíncronas** con Celery + Redis

### Stack Tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Backend API | FastAPI (Python 3.12+) | 0.115.6 |
| ORM | SQLAlchemy 2.0 (async) + Alembic | 2.0.36 |
| Validación | Pydantic v2 + pydantic-settings | 2.10.4 |
| Auth | PyJWT RS256 + passlib (bcrypt) + pyotp | Custom |
| Base de datos | PostgreSQL 16 con RLS | 16+ |
| Cache/Broker | Redis 7 | 5.2.1 (client) |
| Tareas async | Celery 5 | 5.4.0 |
| HTTP Client | httpx | 0.28.1 |
| Testing | Pytest + pytest-asyncio | 8.3.4 |
| Cifrado PII | cryptography (Fernet) | 44.0.0 |

---

## 2. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────┐
│    Cliente (Browser/PWA + Service Worker)        │
│    IndexedDB (offline) + Sync Queue             │
└──────────────────────┬──────────────────────────┘
                       │ HTTPS / REST JSON
┌──────────────────────┴──────────────────────────┐
│               FastAPI Backend                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ API v1   │ │ Auth/JWT │ │ Services Layer   │ │
│  │ (18      │ │ (RS256)  │ │ (Business Logic) │ │
│  │ routers) │ │ + RBAC   │ │                  │ │
│  └─────┬────┘ └────┬─────┘ └────────┬─────────┘ │
│        └───────────┬┘               │            │
│              ┌─────┴────┐    ┌──────┴───────┐    │
│              │ Models   │    │ Celery Tasks │    │
│              │(SQLAlch) │    │ (async jobs) │    │
│              └─────┬────┘    └──────┬───────┘    │
└────────────────────┼────────────────┼────────────┘
                     │                │
          ┌──────────┴───┐    ┌───────┴──────┐
          │ PostgreSQL 16│    │  Redis 7     │
          │ + RLS        │    │  (broker +   │
          │              │    │   cache)     │
          └──────────────┘    └──────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │  External APIs       │
                          │  • NubeFact (SUNAT)  │
                          │  • WhatsApp (Meta)   │
                          └─────────────────────┘
```

### Flujo de una Request Autenticada
1. Cliente envía request con `Authorization: Bearer <JWT>`
2. `get_current_user` dependency decodifica el JWT RS256 con clave pública
3. Se carga el `User` de la DB y se verifica `is_active`
4. Se setea `SET LOCAL app.clinic_id = '<uuid>'` para activar RLS
5. La query SQL solo ve datos de la clínica del usuario (aislamiento automático)
6. El service layer ejecuta la lógica de negocio
7. Se registra en `audit_log` si la operación es sensible

---

## 3. Estructura del Proyecto

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, CORS, lifespan, exception handler, health check
│   ├── config.py                # Pydantic BaseSettings (.env), JWT paths, API keys
│   ├── database.py              # AsyncSession, engine, Base, set_tenant_context(), get_db()
│   │
│   ├── auth/                    # Autenticación y Autorización
│   │   ├── jwt.py               # create_access_token, create_refresh_token, create_mfa_temp_token, decode_token
│   │   ├── dependencies.py      # get_current_user, get_token_payload, require_role() factory
│   │   └── rbac.py              # PERMISSIONS dict, has_permission() — permisos por recurso/acción/rol
│   │
│   ├── core/                    # Utilidades transversales
│   │   ├── security.py          # hash_password, verify_password, encrypt_pii, decrypt_pii (Fernet)
│   │   └── exceptions.py        # CredentialsException(401), ForbiddenException(403), NotFoundException(404),
│   │                            # ConflictException(409), ValidationException(422), TenantException(400)
│   │
│   ├── models/                  # SQLAlchemy 2.0 models (Mapped + mapped_column)
│   │   ├── __init__.py          # Exporta todos los modelos para Alembic autodiscovery
│   │   ├── clinic.py            # Clinic (tenant principal) — name, ruc, settings(JSONB), timezone
│   │   ├── user.py              # User + UserRole enum — email, role, cmp_number, mfa_secret
│   │   ├── patient.py           # Patient — dni(cifrado), dni_hash(SHA-256), allergies(JSONB)
│   │   ├── appointment.py       # Appointment + AppointmentStatus enum + state machine (VALID_TRANSITIONS)
│   │   ├── doctor_schedule.py   # DoctorSchedule — horarios de atención por doctor
│   │   ├── medical_record.py    # MedicalRecord — INSERT-only, cie10_codes(array), content(JSONB), signed_at
│   │   ├── dental_chart.py      # DentalChart — tooth_number(FDI), surfaces, condition, treatment
│   │   ├── prenatal_visit.py    # PrenatalVisit — gestational_week, weight, blood_pressure, labs(JSONB)
│   │   ├── ophthalmic_exam.py   # OphthalmicExam — eye(OD/OS), visual_acuity, sphere, cylinder, iop
│   │   ├── invoice.py           # Invoice + InvoiceItem — TipoComprobante, SunatStatus, FormaPago (SUNAT)
│   │   ├── audit_log.py         # AuditLog — INSERT-only, entity, action, old_data, new_data, ip
│   │   ├── sync_queue.py        # SyncQueue + SyncDeviceMapping — operaciones offline pendientes
│   │   ├── logistica.py         # Supplier, InventoryCategory, InventoryItem, StockMovement (Kardex)
│   │   ├── service.py           # Service — catálogo de servicios médicos por clínica
│   │   └── cash_register.py     # CashSession + CashMovement — control de caja diario
│   │
│   ├── schemas/                 # Pydantic v2 schemas (request/response validation)
│   │   ├── auth.py              # LoginRequest, TokenResponse, RegisterRequest, MFASetup
│   │   ├── clinic.py            # ClinicCreate, ClinicUpdate, ClinicResponse
│   │   ├── user.py              # UserCreate, UserUpdate, UserResponse
│   │   ├── patient.py           # PatientCreate, PatientUpdate, PatientResponse
│   │   ├── appointment.py       # AppointmentCreate, AppointmentUpdate, AppointmentResponse
│   │   ├── medical_record.py    # RecordCreate, RecordResponse
│   │   ├── dental_chart.py      # DentalChartCreate, DentalChartResponse
│   │   ├── prenatal_visit.py    # PrenatalVisitCreate, PrenatalVisitResponse
│   │   ├── ophthalmic_exam.py   # OphthalmicExamCreate, OphthalmicExamResponse
│   │   ├── invoice.py           # InvoiceCreate, InvoiceResponse (SUNAT fields)
│   │   ├── report.py            # DashboardKPIs, RevenueReport
│   │   ├── sync.py              # SyncOperation, SyncBatch, SyncResponse
│   │   ├── logistica.py         # Supplier/Category/Item/StockMovement schemas
│   │   ├── service.py           # ServiceCreate, ServiceResponse
│   │   └── cash_register.py     # CashSession/CashMovement schemas
│   │
│   ├── api/                     # Route handlers
│   │   └── v1/
│   │       ├── router.py        # api_v1_router — agrupa los 18 sub-routers
│   │       ├── auth.py          # POST /auth/login, /auth/register, /auth/refresh, /auth/mfa/*
│   │       ├── clinic.py        # GET/PUT /clinic (perfil de la clínica actual)
│   │       ├── users.py         # CRUD /users (gestión de personal)
│   │       ├── patients.py      # CRUD /patients + búsqueda por DNI
│   │       ├── appointments.py  # CRUD /appointments + PATCH status + availability
│   │       ├── schedules.py     # CRUD /schedules (horarios de doctores)
│   │       ├── public_booking.py# GET/POST /public/booking (reserva online sin auth, con token de clínica)
│   │       ├── records.py       # POST /records, GET /records (HCE — doctor-only create)
│   │       ├── cie10.py         # GET /cie10/search?q=... (búsqueda de códigos CIE-10)
│   │       ├── dental_charts.py # CRUD /dental-charts (odontograma)
│   │       ├── prenatal.py      # CRUD /prenatal (control prenatal)
│   │       ├── ophthalmic.py    # CRUD /ophthalmic (exámenes oftalmológicos)
│   │       ├── invoices.py      # CRUD /invoices + emisión/anulación SUNAT
│   │       ├── reports.py       # GET /reports/dashboard, /reports/revenue, /reports/appointments
│   │       ├── cash_register.py # /cash-register (apertura/cierre de caja, movimientos)
│   │       ├── logistica.py     # /logistica (proveedores, inventario, stock movements/Kardex)
│   │       ├── services.py      # CRUD /services (catálogo de servicios)
│   │       └── sync.py          # POST /sync (sincronización offline batch)
│   │
│   ├── services/                # Business logic layer (separada de los routes)
│   │   ├── auth_service.py      # Login, register, MFA setup/verify, token refresh
│   │   ├── patient_service.py   # CRUD + búsqueda por DNI (cifrado/descifrado Fernet)
│   │   ├── appointment_service.py # CRUD + validación de solapamiento + state machine
│   │   ├── medical_record_service.py # Crear registros (INSERT-only), listar por paciente
│   │   ├── dental_chart_service.py   # CRUD odontograma con historial
│   │   ├── prenatal_service.py       # CRUD fichas prenatales CLAP/SIP
│   │   ├── ophthalmic_service.py     # CRUD exámenes oftalmológicos
│   │   ├── invoice_service.py        # Facturación + integración NubeFact SUNAT
│   │   ├── sunat_service.py          # NubeFact API wrapper (emisión, anulación)
│   │   ├── whatsapp_service.py       # Meta WhatsApp Cloud API wrapper
│   │   ├── cie10_service.py          # Catálogo CIE-10 + búsqueda
│   │   ├── sync_service.py           # Sincronización offline + resolución de conflictos
│   │   ├── audit_service.py          # Registrar operaciones en audit_log
│   │   ├── report_service.py         # KPIs dashboard + reportes de ingresos/citas
│   │   ├── cash_register_service.py  # Apertura/cierre de caja + movimientos
│   │   ├── logistica_service.py      # Proveedores + inventario + Kardex
│   │   └── service_service.py        # CRUD catálogo de servicios
│   │
│   └── tasks/                   # Celery async tasks
│       ├── celery_app.py        # Configuración de Celery (broker + backend Redis)
│       ├── sunat_tasks.py       # Emisión asíncrona de comprobantes SUNAT
│       ├── whatsapp_tasks.py    # Envío de recordatorios WhatsApp (24h, 1h antes)
│       ├── reports_tasks.py     # Generación asíncrona de reportes
│       └── sync_tasks.py       # Procesamiento de batch de sync offline
│
├── alembic/                     # Migraciones de base de datos
│   └── alembic.ini              # Configuración de Alembic
│
├── scripts/
│   ├── generate_keys.py         # Genera par de claves RSA para JWT
│   └── setup_rls.sql            # Script SQL para habilitar RLS en todas las tablas
│
├── tests/
│   └── conftest.py              # Fixtures de pytest (client, db session, test user)
│
├── keys/                        # Claves RSA privada/pública (NO commitear)
├── .env                         # Variables de entorno (NO commitear)
├── .env.example                 # Template de variables de entorno
├── requirements.txt             # Dependencias Python
├── Dockerfile                   # Python 3.12-slim + uvicorn
├── docker-compose.yml           # FastAPI + PostgreSQL 16 + Redis 7 + Celery Worker
├── README.md                    # Plan de hitos (6 hitos, 12 sprints)
└── Arquitectura_Tecnica_SaaS_Clinicas_FastAPI.md  # Documento de arquitectura técnica
```

---

## 4. Módulos en Detalle

### 4.1 Configuración (`app/config.py`)
- Usa `pydantic-settings.BaseSettings` para cargar variables de `.env`
- Cached con `@lru_cache` via `get_settings()`
- Properties computados: `jwt_private_key`, `jwt_public_key` (leen archivos PEM), `is_production`
- Secciones: App, Server, Database, Redis, JWT, Encryption, CORS, Celery, NubeFact, WhatsApp

### 4.2 Base de Datos (`app/database.py`)
- Engine async: `create_async_engine` con pool_size=20, max_overflow=10
- Session factory: `async_sessionmaker` con `expire_on_commit=False`
- Base declarativa: `class Base(DeclarativeBase)`
- `set_tenant_context()`: ejecuta `SET LOCAL app.clinic_id = '<uuid>'` para RLS
- `get_db()`: dependency que auto-commit/rollback/close la sesión

### 4.3 Autenticación (`app/auth/`)

#### JWT (`jwt.py`)
- **Access token**: 15 min, payload: `{sub, clinic_id, role, type:"access"}`
- **Refresh token**: 7 días, payload: `{sub, clinic_id, type:"refresh"}`
- **MFA temp token**: 5 min (para completar flujo TOTP)
- Codificación con clave privada RSA, decodificación con clave pública

#### Dependencies (`dependencies.py`)
- `get_current_user`: decodifica JWT → carga User → setea RLS tenant context
- `get_token_payload`: decodifica JWT sin consultar DB (ligero)
- `require_role(*roles)`: factory que retorna dependency que verifica rol del usuario

#### RBAC (`rbac.py`)
- Diccionario `PERMISSIONS` mapea `{recurso: {acción: [roles]}}` para 7 recursos
- Restricción clave: `receptionist` NO puede ver `medical_record` (NTS 139)
- `medical_record` no tiene `update`/`delete` (INSERT-only por normativa)

### 4.4 Modelos de Datos (`app/models/`)

Todos los modelos usan:
- `UUID(as_uuid=True)` como PK con `default=uuid.uuid4`
- `clinic_id` como FK a `clinics.id` (para RLS)
- `created_at`/`updated_at` con `server_default=func.now()`
- Mapped annotations de SQLAlchemy 2.0

**Modelos registrados** (19 tablas):

| Modelo | Tabla | Descripción |
|---|---|---|
| `Clinic` | clinics | Tenant principal, RUC, timezone, settings(JSONB) |
| `User` | users | Usuarios + UserRole enum (4 roles) + MFA |
| `Patient` | patients | Pacientes, DNI cifrado (Fernet) + SHA-256 hash para búsqueda |
| `Appointment` | appointments | Citas + state machine (6 estados, transiciones validadas) |
| `DoctorSchedule` | doctor_schedules | Horarios de atención por doctor |
| `MedicalRecord` | medical_records | HCE INSERT-only, CIE-10, JSONB content, firma digital |
| `DentalChart` | dental_charts | Odontograma (sistema FDI) |
| `PrenatalVisit` | prenatal_visits | Control prenatal CLAP/SIP |
| `OphthalmicExam` | ophthalmic_exams | Exámenes oftalmológicos (OD/OS, refracción, PIO) |
| `Invoice` | invoices | Facturación SUNAT (serie, correlativo, IGV, NubeFact) |
| `InvoiceItem` | invoice_items | Ítems de factura |
| `AuditLog` | audit_log | Auditoría INSERT-only, retención 10 años |
| `SyncQueue` | sync_queue | Cola de operaciones offline |
| `SyncDeviceMapping` | sync_device_mappings | Mapeo local_id ↔ server_id |
| `Supplier` | suppliers | Proveedores (logística) |
| `InventoryCategory` | inventory_categories | Categorías de inventario |
| `InventoryItem` | inventory_items | Artículos de inventario + stock |
| `StockMovement` | stock_movements | Kardex de movimientos de stock |
| `Service` | services | Catálogo de servicios médicos |
| `CashSession` | cash_sessions | Sesión de caja (apertura/cierre) |
| `CashMovement` | cash_movements | Movimientos de caja (ingresos/egresos) |

### 4.5 State Machine de Citas

```
scheduled → confirmed → in_progress → completed
    ↓           ↓
 cancelled   cancelled
    ↓           ↓
  no_show     no_show
```

Validada por `is_valid_transition()` y el diccionario `VALID_TRANSITIONS` en `models/appointment.py`.

### 4.6 API Routes (`app/api/v1/`)

18 sub-routers registrados en `router.py` bajo el prefijo `/api/v1`:

| Prefijo | Router | Tags | Descripción |
|---|---|---|---|
| `/auth` | auth | Autenticación | Login, register, refresh, MFA |
| `/clinic` | clinic | Clínica | Perfil de la clínica actual |
| `/users` | users | Usuarios | CRUD de personal de la clínica |
| `/patients` | patients | Pacientes | CRUD + búsqueda por DNI |
| `/appointments` | appointments | Citas | CRUD + status change + availability |
| `/schedules` | schedules | Horarios | Horarios de doctores |
| `/public/booking` | public_booking | Reserva Pública | Reserva online (sin auth) |
| `/records` | records | HCE | Historia clínica (doctor-only) |
| `/cie10` | cie10 | CIE-10 | Búsqueda de códigos CIE-10 |
| `/dental-charts` | dental_charts | Odontograma | Odontograma por diente |
| `/prenatal` | prenatal | Control Prenatal | Fichas prenatales CLAP/SIP |
| `/ophthalmic` | ophthalmic | Oftalmología | Exámenes oftalmológicos |
| `/invoices` | invoices | Facturación SUNAT | Emisión de comprobantes |
| `/reports` | reports | Reportes | Dashboard KPIs, revenue, citas |
| `/cash-register` | cash_register | Caja | Control de caja diario |
| `/logistica` | logistica | Logística | Proveedores, inventario, Kardex |
| `/services` | services | Servicios | Catálogo de servicios |
| `/sync` | sync | Sincronización | Sync offline batch |

### 4.7 Services Layer (`app/services/`)

Capa de lógica de negocio separada de los routes. Patrones comunes:
- Reciben una `AsyncSession` de SQLAlchemy como parámetro
- Usan `select()` / `insert()` de SQLAlchemy 2.0
- Lanzan excepciones de `app.core.exceptions` para errores de negocio
- Interactúan con el `audit_service` para registrar operaciones sensibles

### 4.8 Celery Tasks (`app/tasks/`)

- `celery_app.py`: Celery instance con broker y backend Redis
- `sunat_tasks.py`: Emisión asíncrona de facturas/boletas a NubeFact, reintentos
- `whatsapp_tasks.py`: Envío de recordatorios de cita (24h, 1h antes) vía Meta Cloud API
- `reports_tasks.py`: Generación asíncrona de reportes pesados
- `sync_tasks.py`: Procesamiento de batch de sync desde dispositivos offline

---

## 5. Seguridad y Cumplimiento Legal

### Capas de Seguridad

| Capa | Implementación | Normativa |
|---|---|---|
| Autenticación | JWT RS256 (15 min) + refresh (7 días) + TOTP MFA | RENHICE |
| Autorización | RBAC (4 roles) + RLS PostgreSQL | NTS 139 Cap. VII |
| Cifrado PII | Fernet (dni, phone, email) + SHA-256 hash para búsqueda | Ley 29733, DS 016-2024 |
| Hashing | bcrypt via passlib | — |
| Audit trail | tabla INSERT-only, sin UPDATE/DELETE, retención 10 años | Ley 30024 |
| Multi-tenancy | RLS `USING (clinic_id = current_setting('app.clinic_id')::uuid)` | — |
| HCE inmutable | MedicalRecord INSERT-only, signed_at como firma digital | NTS 139-MINSA |

### Campos PII Cifrados (Fernet)
- `patients.dni` (+ `dni_hash` SHA-256 para búsquedas indexadas)
- `patients.phone`
- `patients.email`
- `patients.emergency_contact_phone`

---

## 6. Multi-Tenancy (RLS)

Cada tabla con datos de clínica tiene `clinic_id`. Las políticas RLS:

```sql
ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY;
CREATE POLICY <tabla>_clinic_isolation ON <tabla>
    USING (clinic_id = current_setting('app.clinic_id')::uuid);
```

El tenant se setea en `get_current_user` antes de cada query:
```python
await session.execute(text(f"SET LOCAL app.clinic_id = '{clinic_id}'"))
```

Tablas con RLS: `users`, `patients`, `audit_log`, `appointments`, `doctor_schedules`, `medical_records`, `dental_charts`, `prenatal_visits`, `ophthalmic_exams`, `invoices`, `sync_queue`, `sync_device_mappings`.

---

## 7. Sincronización Offline

### Flujo
1. Cliente opera offline, guarda en IndexedDB + cola de sync
2. Al reconectar, envía batch a `POST /api/v1/sync`
3. Backend aplica operaciones con resolución de conflictos (last-write-wins)
4. Responde con: `applied` (exitosas), `conflicts` (conflictos), `updates` (cambios del servidor)

### Modelos
- `SyncQueue`: batch de operaciones (entity, action, data, timestamp)
- `SyncDeviceMapping`: mapeo `local_id` ↔ `server_id` para entidades creadas offline

---

## 8. Convenciones y Patrones de Código

### Estructura de archivos
- **Un modelo por archivo** en `models/`, nombre singular (`patient.py`, no `patients.py`)
- **Un schema module por modelo** en `schemas/`, con sufijos `Create`, `Update`, `Response`
- **Un service por módulo** en `services/`, sufijo `_service.py`
- **Un router por módulo** en `api/v1/`, nombre plural (`patients.py`, `invoices.py`)
- **Una task por integración** en `tasks/`, sufijo `_tasks.py`

### Patrones SQLAlchemy
- Mapped annotations: `Mapped[type] = mapped_column(...)` (SQLAlchemy 2.0 style)
- UUIDs como PKs: `UUID(as_uuid=True), primary_key=True, default=uuid.uuid4`
- Todos los modelos heredan de `Base` (`app.database.Base`)
- Índices explícitos en `__table_args__` para queries frecuentes

### Patrones FastAPI
- Dependencies inyectadas via `Depends()`
- `get_current_user` para auth, `require_role()` para RBAC
- `get_db()` para sesión de DB (auto-commit/rollback)
- Exception handlers globales en `main.py`
- CORS configurado vía `settings.CORS_ORIGINS`

### Convenciones de nombres
- Modelos: PascalCase, singular (`Patient`, `Invoice`)
- Tablas: snake_case, plural (`patients`, `invoices`)
- Enums: PascalCase con valores snake_case (`UserRole.CLINIC_ADMIN`)
- API paths: kebab-case (`/dental-charts`, `/cash-register`)
- Services: snake_case con sufijo `_service` (`patient_service.py`)

### Idioma
- Código (variables, funciones, clases): **Inglés**
- Comentarios y docstrings: **Español** (mayoritariamente)
- API tags: **Español** (`"Pacientes"`, `"Facturación SUNAT"`)
- Mensajes de error: **Español** (`"Credenciales inválidas"`, `"Recurso no encontrado"`)

---

## 9. Infraestructura y DevOps

### Docker Compose (desarrollo)
```
services:
  api:           # FastAPI + uvicorn --reload (puerto 8000)
  postgres:      # PostgreSQL 16 Alpine (puerto 5432)
  redis:         # Redis 7 Alpine (puerto 6379)
  celery_worker: # Celery worker
```

### Comandos Esenciales

```bash
# Iniciar servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker
docker-compose up -d

# Migraciones
alembic upgrade head              # Aplicar migraciones
alembic revision --autogenerate -m "descripción"  # Crear migración

# Generar claves RSA para JWT
python scripts/generate_keys.py

# Setup RLS (después de migración inicial)
psql -U postgres -d clinicas_db -f scripts/setup_rls.sql

# Tests
pytest tests/

# Celery worker
celery -A app.tasks.celery_app worker --loglevel=info
```

### Endpoints útiles
- `GET /health` — Health check
- `GET /docs` — Swagger UI (OpenAPI)
- `GET /redoc` — ReDoc

---

## 10. Guía para Contribuidores / Agentes

### Al agregar un nuevo módulo:
1. Crear modelo en `app/models/<nombre>.py` (heredar de `Base`, incluir `clinic_id`)
2. Registrar en `app/models/__init__.py`
3. Crear schemas en `app/schemas/<nombre>.py` (`Create`, `Update`, `Response`)
4. Crear service en `app/services/<nombre>_service.py`
5. Crear router en `app/api/v1/<nombre>.py`
6. Registrar router en `app/api/v1/router.py`
7. Crear migración: `alembic revision --autogenerate`
8. Agregar RLS en `scripts/setup_rls.sql`
9. Actualizar RBAC en `app/auth/rbac.py` si aplica

### Al modificar código existente:
- Respetar la separación de capas: Route → Service → Model
- No poner lógica de negocio en los routes
- Usar las excepciones personalizadas de `app/core/exceptions.py`
- Registrar operaciones sensibles en `audit_log`
- Siempre cifrar campos PII con `encrypt_pii()` / `decrypt_pii()`
- Respetar la inmutabilidad de `MedicalRecord` y `AuditLog` (INSERT-only)

### Testing
- Framework: pytest + pytest-asyncio
- Fixtures en `tests/conftest.py`
- Tests de integración deben verificar aislamiento RLS entre tenants
