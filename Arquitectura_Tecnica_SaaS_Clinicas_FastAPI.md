> **ARQUITECTURA** **TÉCNICA** SaaS de Gestión para Clínicas
> Especializadas


> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**Índice**

Índice......................................................................................................................................................2 1.
Stack Tecnológico
Completo................................................................................................................3
1.1 Visión general del
stack..................................................................................................................3
2. Arquitectura del
Sistema......................................................................................................................5
2.1 Diagrama de
componentes.............................................................................................................5
2.2 Flujo de datos offline-first
...............................................................................................................5
3. Backend: FastAPI en
Detalle...............................................................................................................7
3.1 Estructura del
proyecto...................................................................................................................7
3.2 Endpoint de sincronización
offline...................................................................................................8
4. Base de Datos: PostgreSQL con
RLS..................................................................................................9
4.1 Multi-tenancy con Row-Level
Security............................................................................................9
4.2 Modelo de datos
principal...............................................................................................................9
5. Frontend: Next.js + PWA
Offline-First.................................................................................................11
5.1 Estructura del proyecto
frontend...................................................................................................11
5.2 Flujo de offline con
Dexie.js..........................................................................................................11
6. Infraestructura y
Costos.....................................................................................................................13
6.1 Hosting y
deployment...................................................................................................................13
6.2 Costos de integraciones
externas.................................................................................................13
7. Seguridad y
Cumplimiento.................................................................................................................14
7.1 Capas de seguridad
implementadas.............................................................................................14
8. Plan de Sprints (12
semanas)............................................................................................................15
8.1 Presupuesto estimado del
MVP....................................................................................................15

> Pág. 2
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*
>
> **1.** **Stack** **Tecnológico** **Completo**
>
> La arquitectura separa frontend y backend en dos servicios
> independientes, comunicados vía REST API con OpenAPI/Swagger
> autogenerado. Esta separación permite escalar cada componente de forma
> independiente y facilita la contratación de freelancers
> especializados.
>
> **1.1** **Visión** **general** **del** **stack**

>Capa Tecnología Versión Justificación
>Frontend Next.js 14+ (App Router) 14.2+SSR/SSG, React Server Components, pool masivo de freelancers
>UI Components shadcn/ui + Tailwind CSS Latest Componentes accesibles, rápido desarrollo, fácil theming
>Backend API FastAPI (Python 3.12+) 0.110+ Async nativo, Pydantic v2,autodocs OpenAPI, integración directa con ML
>ORM SQLAlchemy 2.0 + Alembic 2.0+ ORM maduro, async support,migraciones robustas
>Validación Pydantic v2 2.6+ Schemas compartidos API/DB, validación CIE-10 nativa
>Auth FastAPI + JWT (PyJWT) Custom Tokens asimétricos RS256, refresh tokens, RBAC granular
>Base de datos PostgreSQL 16 16+ RLS multi-tenant, JSONB para HCE flexible, audit triggers
>Cache Redis (Upstash) 7+ Rate limiting, cache de sesiones, colas de background jobs
>Tareas async Celery + Redis broker 5.3+ Jobs SUNAT, WhatsApp, sync offline, reportes
>Offline/PWA Service Workers + IndexedDB Web API Funcionalidad sin internet — requisito crítico para Huánuco
>Testing Pytest + Playwright Latest Unit/integration backend, E2E frontend


> **¿Por** **qué** **FastAPI** **y** **no** **Django?**
>
> Django es excelente para proyectos monolíticos con su admin panel y
> ORM. Pero para este SaaS, FastAPI es superior porque: (1) El frontend
> ya lo maneja Next.js, así que no necesitamos templates de Django. (2)
> FastAPI es 3-5x más rápido en benchmarks de API REST. (3) Pydantic v2
> valida datos médicos (formatos CIE-10, DNI, RUC) de forma nativa y con
> tipado estricto. (4) La autodocumentación Swagger en /docs permite a
> freelancers entender la API sin documentación extra. (5) La
> integración con librerías ML (Whisper, scikit-learn, transformers) es
> import directo sin wrappers.
>
> **Ventaja** **estratégica:** **Python** **+** **IA/ML**
>
> Pág. 3
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

Con Python como backend, el roadmap de IA se simplifica enormemente:
transcripción de voz a notas clínicas (Whisper), auto-sugerencia de
códigos CIE-10 (sentence-transformers + búsqueda semántica), predicción
de no-shows (scikit-learn), y análisis de imágenes médicas (PyTorch).
Todo esto se integra directamente como endpoints FastAPI sin necesidad
de microservicios separados en la fase inicial.

> Pág. 4
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**2.** **Arquitectura** **del** **Sistema**

**2.1** **Diagrama** **de** **componentes**

La arquitectura sigue un patrón de API Gateway donde Next.js actúa como
BFF (Backend for Frontend) y FastAPI como servicio de lógica de negocio:

> ┌─────────────────────────────────────────────────────────────┐ │
> USUARIO (Browser/Móvil) │ │ PWA + Service Worker + IndexedDB
> (OFFLINE-FIRST) │
> └─────────────────────────────┬───────────────────────────────┘
>
> │ HTTPS ┌─────────┴──────────┐
>
> │ NEXT.JS (Vercel)
>
> │ SSR / API Routes

│ Frontend + BFF

│ Auth cookies

> └─────────┬──────────┘
>
> │ REST API (JSON) ┌─────────┴──────────┐
>
> │ FASTAPI (Railway/
>
> │ Render / AWS ECS)

│ Business logic

│ Pydantic models

> └───┬─────┬─────┬────┘ │ │ │
>
> ┌─────┴─┐ ┌─┴───┐ ┌┴──────┐ │Postgre│ │Redis│ │Celery │ │SQL+RLS│
> │Cache│ │Workers│ └───────┘ └─────┘ └─┬─────┘
>
> │ ┌─────────────┴─────────────┐ │ NubeFact │ WhatsApp │ S3 │ │ (SUNAT)
> │ (Meta) │ │ └───────────────────────────┘

**2.2** **Flujo** **de** **datos** **offline-first**

El offline-first es el diferenciador competitivo clave del producto. El
frontend funciona como una aplicación autónoma cuando no hay internet,
sincronizando con el backend cuando la conexión regresa.

> MODO ONLINE:
>
> MODO OFFLINE:
>
> RECONEXION:

Usuario → React UI → API call → FastAPI → PostgreSQL ↓ (simultáneo)

> IndexedDB (cache local)

Usuario → React UI → IndexedDB (lectura/escritura) ↓

> Sync Queue (operaciones pendientes)

Sync Queue → FastAPI /api/sync endpoint

> ↓ (batch de operaciones con timestamps) FastAPI resuelve conflictos
> (last-write-wins)
>
> ↓
>
> Responde con datos actualizados → IndexedDB
>
> Pág. 5
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**Qué** **funciona** **offline** **vs.** **qué** **requiere**
**internet**

OFFLINE: consultar pacientes, crear/editar citas, registrar notas
clínicas, ver odontograma, llenar fichas obstétricas, generar recibos
preliminares, ver agenda del día. REQUIERE INTERNET: emitir
facturas/boletas SUNAT (validación en tiempo real), enviar WhatsApp,
sincronizar entre dispositivos, descargar actualizaciones. Las
operaciones SUNAT yWhatsApp se encolan y procesan automáticamente al
reconectar.

> Pág. 6
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**3.** **Backend:** **FastAPI** **en** **Detalle**

**3.1** **Estructura** **del** **proyecto**

> backend/ ├── app/
>
> │ ├── main.py
>
> │ ├── config.py │ ├── database.py
>
> │ ├── auth/

\# FastAPI app, CORS, middleware

\# Settings con Pydantic BaseSettings

\# AsyncSession, engine, RLS setup

> │ │ ├── jwt.py
>
> │ │ ├── dependencies.py
>
> │ │ └── rbac.py

\# Crear/verificar JWT RS256

\# get_current_user, require_role

\# Roles: admin, doctor, receptionist

> │ ├── models/ \# SQLAlchemy models
>
> │ │ ├── clinic.py │ │ ├── user.py
>
> │ │ ├── patient.py
>
> │ │ ├── appointment.py

\# Clinic (tenant), con RUC \# User + roles + CMP number \# Patient con
DNI identifier

\# Citas con state machine

> │ │ ├── medical_record.py# HCE con JSONB + CIE-10
>
> │ │ ├── invoice.py
>
> │ │ └── audit_log.py

\# Facturación SUNAT fields

\# Inmutable, INSERT-only

> │ ├── schemas/ \# Pydantic v2 schemas
>
> │ │ ├── patient.py \# PatientCreate, PatientResponse │ │ ├──
> appointment.py
>
> │ │ ├── medical_record.py# Con validación CIE-10
>
> │ │ ├── invoice.py
>
> │ │ └── sync.py

\# SUNAT-compliant fields

\# SyncBatch, SyncResponse

> │ ├── api/ \# Route handlers │ │ ├── v1/
>
> │ │ │ ├── auth.py
>
> │ │ │ ├── patients.py

\# Login, refresh, MFA

> \# CRUD pacientes
>
> │ │ │ ├── appointments.py
>
> │ │ │ ├── records.py │ │ │ ├── invoices.py │ │ │ ├── sync.py
>
> │ │ │ └── reports.py

\# HCE endpoints \# SUNAT billing

\# Offline sync endpoint

\# Dashboard KPIs

> │ ├── services/ \# Business logic layer
>
> │ │ ├── sunat_service.py \# NubeFact API integration │ │ ├──
> whatsapp_service.py \# Meta Cloud API
>
> │ │ ├── sync_service.py \# Conflict resolution │ │ └──
> cie10_service.py \# CIE-10 lookup + ML │ ├── tasks/ \# Celery async
> tasks
>
> │ │ ├── sunat_tasks.py \# Emisión de comprobantes │ │ ├──
> whatsapp_tasks.py# Recordatorios
>
> │ │ └── reports_tasks.py \# Generación de reportes
>
> │ └── core/
>
> │ ├── security.py
>
> │ └── exceptions.py

\# Hashing, encryption

\# Custom HTTP exceptions

> ├── alembic/ ├── tests/
>
> ├── requirements.txt ├── Dockerfile
>
> └── docker-compose.yml

\# Migraciones DB

> \# Dev: FastAPI + PG + Redis
>
> Pág. 7
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**3.2** **Endpoint** **de** **sincronización** **offline**

El endpoint más crítico del sistema. Recibe un batch de operaciones
creadas offline y las aplica con resolución de conflictos:

> \# POST /api/v1/sync
>
> class SyncOperation(BaseModel):
>
> entity: Literal\['patient','appointment','record'\] action:
> Literal\['create','update'\]
>
> local_id: str data: dict
>
> timestamp: datetime

\# UUID generado en cliente \# Payload de la entidad

\# Momento de la operación local

> class SyncBatch(BaseModel): operations: list\[SyncOperation\]
>
> last_sync: datetime \# Última sincronización exitosa
>
> class SyncResponse(BaseModel):
>
> applied: list\[dict\] conflicts: list\[dict\]
>
> updates: list\[dict\]

\# {local_id, server_id, status} \# {local_id, server_version}

\# Cambios del servidor desde last_sync

La resolución de conflictos usa last-write-wins con timestamp del
cliente. Si dos dispositivos modifican el mismo registro, gana el
timestamp más reciente. Para registros médicos (que son inmutables por
normativa), los conflictos de creación nunca ocurren porque cada nota
clínica es un INSERT nuevo — nunca un UPDATE.

> Pág. 8
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*
>
> **4.** **Base** **de** **Datos:** **PostgreSQL** **con** **RLS**
>
> **4.1** **Multi-tenancy** **con** **Row-Level** **Security**
>
> Cada tabla tiene una columna clinic_id. PostgreSQL enforces aislación
> de datos a nivel de base de datos mediante políticas RLS, garantizando
> que una clínica jamás pueda ver datos de otra:
>
> -- Habilitar RLS en tabla de pacientes
>
> ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
>
> -- Política: solo ver pacientes de tu clínica CREATE POLICY
> patients_isolation ON patients
>
> USING (clinic_id = current_setting('app.clinic_id')::uuid);
>
> -- En cada request, FastAPI setea el contexto: async def
> set_tenant(session, clinic_id):
>
> await session.execute(
>
> text("SET LOCAL app.clinic_id = :cid"), {"cid": str(clinic_id)}
>
> )
>
> **4.2** **Modelo** **de** **datos** **principal**

>Tabla Campos clave Notas
>clinics id, name, ruc, address, phone,specialty_type, timezone, settings(JSONB) Tenant principal. RUC validado con SUNAT API
>users id, clinic_id, email, hashed_password,role (enum), cmp_number, specialty,is_mfa_enabled Roles: super_admin, clinic_admin, doctor, receptionist
>patients id, clinic_id, dni, first_name, last_name, birth_date, phone, email, blood_type,allergies (JSONB) DNI como identificador único per NTS 139. Búsqueda por DNI indexada
>appointments id, clinic_id, patient_id, doctor_id, start_time, end_time, status (enum),service_type, notes Status: scheduled, confirmed, in_progress, completed, no_show, cancelled
>medical_records id, clinic_id, patient_id, doctor_id,record_type, cie10_codes (array), content(JSONB), specialty_data (JSONB),signed_at INSERT-only. JSONB permite datos flexibles por especialidad. signed_at = firma digital 
>dental_charts id, record_id, tooth_number (FDI), surfaces, condition, treatment, notes Vinculado a medical_record. Historial versionado del odontograma
>prenatal_visits id, record_id, gestational_week, weight, blood_pressure, uterine_height, fetal_hr, presentation, labs (JSONB) Datos específicos de control prenatal CLAP/SIP
>ophthalmic_exams id, record_id, eye (OD/OS), visual_acuity, sphere, cylinder, axis, addition, iop, notes Refracción + PIO + campos adicionales en JSONB
>invoices id, clinic_id, patient_id, serie, correlativo, tipo_doc (F/B), igv, total sunat_status, nubefact_response (JSONB) Campos SUNAT: serie, correlativo, tipo_comprobante, moneda, forma_pago
>audit_log id, clinic_id, user_id, entity, entity_id, action, old_data, new_data, ip user_agent, created_at INMUTABLE. Sin permisos UPDATE/DELETE. Retención: 10 años (requisito legal)
>sync_queue id, clinic_id, device_id, operations (JSONB), status, created_at, processed_at Cola de operaciones offline pendientes de procesar
> Pág. 9
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

||
||
||
||
||
||
||

> Pág. 10
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**5.** **Frontend:** **Next.js** **+** **PWA** **Offline-First**

**5.1** **Estructura** **del** **proyecto** **frontend**

> frontend/ ├── src/
>
> │ ├── app/ \# Next.js App Router
>
> │ │ ├── (auth)/
>
> │ │ ├── (dashboard)/

\# Login, registro

\# Layout principal autenticado

> │ │ │ ├── citas/
>
> │ │ │ ├── pacientes/ │ │ │ ├── hce/
>
> │ │ │ ├── facturacion/
>
> │ │ │ ├── reportes/

\# Calendario + agenda \# Lista + ficha

\# Historia clínica + especialidades \# SUNAT billing

\# Dashboard KPIs

> │ │ │ └── configuracion/# Clínica, usuarios, roles
>
> │ │ └── api/ \# Next.js API routes (proxy a FastAPI) │ ├── components/
>
> │ │ ├── ui/
>
> │ │ ├── calendar/ │ │ ├── odontogram/ │ │ ├── prenatal/ │ │ ├──
> ophthalmic/
>
> │ │ └── offline/

\# shadcn/ui components \# Calendario de citas

\# Odontograma interactivo \# Ficha prenatal + curvas \# Ficha
oftalmológica

\# Indicador de estado + sync

> │ ├── lib/
>
> │ │ ├── api-client.ts │ │ ├── offline-db.ts
>
> │ │ ├── sync-manager.ts
>
> │ │ └── auth.ts
>
> \# Fetch wrapper con retry + offline \# IndexedDB con Dexie.js
>
> \# Cola de sync + Background Sync

\# JWT storage + refresh

> │ └── hooks/
>
> │ ├── useOffline.ts │ ├── useSync.ts
>
> │ └── usePatients.ts

\# Estado online/offline \# Trigger sync manual

\# Queries con fallback offline

> ├── public/
>
> │ ├── sw.js
>
> │ └── manifest.json

\# Service Worker

\# PWA manifest

> └── next.config.js

**5.2** **Flujo** **de** **offline** **con** **Dexie.js**

Dexie.js es un wrapper de IndexedDB que simplifica enormemente el
almacenamiento local. El patrón es: toda lectura primero consulta
IndexedDB, y toda escritura va a IndexedDB + cola de sync:

> // lib/offline-db.ts import Dexie from 'dexie';
>
> class ClinicDB extends Dexie { patients: Dexie.Table; appointments:
> Dexie.Table; records: Dexie.Table; syncQueue: Dexie.Table;
>
> Pág. 11
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*
>
> constructor() { super('ClinicDB'); this.version(1).stores({
>
> patients: 'id, dni, lastName, \*tags', appointments: 'id, date,
> doctorId, status', records: 'id, patientId, createdAt', syncQueue:
> '++id, entity, action, timestamp'
>
> }); }

}

// Uso: guardar paciente offline async function savePatient(data) {

> const localId = crypto.randomUUID();
>
> await db.patients.put({ ...data, id: localId }); await
> db.syncQueue.add({
>
> entity: 'patient', action: 'create', localId, data, timestamp: new
> Date()

}); }

> Pág. 12
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*
>


> **Tip:** **Railway.app** **para** **FastAPI**
>
> Railway.app es la opciónmás simple para deployar FastAPI: conectas tu
> repo de GitHub, Railway detecta el Dockerfile, y deploya
> automáticamente en cada push. Incluye dominio HTTPS, logs en tiempo
> real, y escalado automático. El plan Starter (\$5/mes) incluye 8GB RAM
> y 8 vCPU compartidos — más que suficiente para \<100 clínicas.
> Render.com (\$7/mes) es la alternativa si Railway no está disponible.
>
> Pág. 13
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*
>
> **7.** **Seguridad** **y** **Cumplimiento**
>
> **7.1** **Capas** **de** **seguridad** **implementadas**

>Capa Implementación Normativa
>Transporte TLS 1.2+ automático (Vercel + Railway). HSTS habilitado Ley 29733 Art. 39
>Reposo (DB) AWS RDS encryption at rest (AES-256). Backup cifrado NTS 139-MINSA
>Reposo (S3) S3 Server-Side Encryption con AWS KMS Ley 29733
>Aplicación Campos PII cifrados con Fernet (cryptography lib). DNI, teléfono, email DS 016-2024-JUS
>Autenticación JWT RS256 (15 min) + refresh token (7
días). MFA obligatorio para doctors/admins (TOTP) RENHICE Art. 8
>Autorización RBAC + RLS PostgreSQL. Doctor solo accede a sus pacientes. Receptionist no ve HCE NTS 139 Cap. VII
>Audit Trail Tabla inmutable (INSERT-only). Registra: usuario, acción, entidad, IP,timestamp, old/new values Ley 30024 Art. 15
>Datos offline IndexedDB cifrado con Web Crypto API. Auto-borrado al cerrar sesión Ley 29733 Art. 39
>Incidentes Notificación a ANPDP en 48h. Log de incidentes separado DS 016-2024 Art. 28

> Pág. 14
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*
>
> **8.** **Plan** **de** **Sprints** **(12** **semanas)**
>
> Organización del desarrollo del MVP en 6 sprints de 2 semanas,
> optimizado para un equipo de 1 founder + 1-2 freelancers:

>Sprint Entregables Backend (FastAPI) Frontend (Next.js)
>S1-S2 (Sem 1-4) Auth + multi-tenant + modelo de datos + CRUD pacientes Setup FastAPI +SQLAlchemy + Alembic. Auth JWT. CRUD patients API. RLS config Next.js shell + shadcn/ui. Login/register. Patient list + profile
>S3-S4 (Sem 5-8) Calendario de citas + reserva online + estados de cita Appointments API con state machine. Disponibilidad en tiempo real Calendario interactivo (react-big-calendar). Link de reserva público
>S5-S6 (Sem 9-12) HCE base + odontograma + fichas especialidad Medical records API(JSONB). Dental chart API. Prenatal + ophthalmic Motor HCE dinámico. Odontograma SVG interactivo.Fichas por especialidad
>S7-S8 (Sem 13-16) Facturación SUNAT + WhatsApp reminders NubeFact integration (Celery task).Meta WhatsApp API. Cron de recordatorios UI de facturación. Configuración de recordatorios. Reportes básicos
>S9-S10 (Sem 17-20) Offline-first PWA + sincronización Sync endpoint. Conflict resolution.Background job de sync Service Worker.IndexedDB con Dexie. Sync manager. Indicador offline
>S11-S12(Sem 21-24) Testing + QA + polish + preparación beta Pytest suite completo. Load testing. Security audit. Docs API Playwright E2E. PWA audit (Lighthouse >90).Responsive. Onboarding

> **8.1** **Presupuesto** **estimado** **del** **MVP**

||
||
||
||
||
||
||
||
||
||
||
||

> Pág. 15
>
> *Arquitectura* *Técnica* *—* *SaaS* *Clínicas*

**Próximos** **pasos** **inmediatos**

1\. Crear repositorios en GitHub: backend/ y frontend/ (o monorepo con
Turborepo) 2. Configurar entorno Docker local: docker-compose con
FastAPI + PostgreSQL + Redis 3. Publicar brief de contratación en
Workana/Torre.ai para freelancer Python/FastAPI 4. Iniciar diseño en
Figma usando el kit Preclinic como base 5. Crear cuenta sandbox en
NubeFact para pruebas de facturación 6. Registrar cuenta Meta Business
para WhatsApp API

> Pág. 16
