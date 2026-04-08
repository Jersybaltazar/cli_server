# Fase 2 — Módulo Recetas Médicas (Avanzado)

> Continuación del módulo Recetas Médicas (Fase 1 ya implementada). Esta fase incorpora el cumplimiento normativo total para Perú: catálogo DIGEMID, recetas controladas (psicotrópicos/estupefacientes), validación de interacciones medicamentosas, y firma electrónica con QR para verificación pública.

**Versión del plan:** 1.0
**Fecha:** 2026-04-08
**Estado de Fase 1:** ✅ Completada (recetas comunes, plantillas, PDF, firma simple)

---

## 1. Resumen ejecutivo

La Fase 1 entregó un MVP funcional de recetas comunes con:
- CRUD de recetas (encabezado + N items de medicamento, texto libre)
- Plantillas reutilizables ("recetas frecuentes") por clínica
- PDF con membrete vía WeasyPrint
- Firma digital simple (timestamp + user_id) con inmutabilidad post-firma
- DNI desencriptado en respuesta y PDF

La Fase 2 cierra los gaps regulatorios y de seguridad clínica que hoy obligarían al médico a usar otra herramienta para casos especiales:

| Gap (hoy) | Fase 2 lo resuelve con |
|---|---|
| Texto libre en medicamento → riesgo de typo, no estandarizado | Catálogo DIGEMID con autocomplete por DCI |
| No se pueden prescribir psicotrópicos/estupefacientes | Recetario especial numerado, listas IIA/IIIA-C, validación 3 días |
| Sin alerta de interacciones peligrosas | DDI checker contra base local sembrada de RxNav/DrugBank no comercial |
| Firma simbólica no verificable externamente | QR en PDF que apunta a endpoint público de verificación |
| Sin trazabilidad de impresión / dispensación | Log de descargas + hash del PDF |
| Sin numeración correlativa por clínica | Secuencia `prescription_sequence` análoga a `lab_sequence` |

Fase 2 es modular: cada bloque (catálogo, controlados, DDI, QR) puede activarse/desactivarse independientemente vía feature flag de clínica. Una clínica que solo necesita el catálogo no se ve obligada a operar el flujo de psicotrópicos.

---

## 2. Marco normativo investigado

Los componentes del plan se justifican contra los siguientes instrumentos legales peruanos vigentes:

### 2.1 Receta común
- **Ley 26842 — Ley General de Salud** — establece la receta médica como acto profesional.
- **DS 014-2011-SA — Reglamento de Establecimientos Farmacéuticos** — define que la prescripción debe ser "obligatoria por DCI", sin enmendaduras, y enumera datos mínimos.
- **DS 016-2011-SA / DS 004-2023-SA** — modificatorias y manual de buenas prácticas de prescripción.

**Datos mínimos de la receta común** (cubiertos parcialmente en Fase 1, completados aquí):
- Prescriptor: nombre, **CMP**, dirección y teléfono del consultorio, **sello**.
- Paciente: nombre, **edad**, **sexo**, DNI, peso (en pediátricos).
- Medicamento: **DCI obligatoria**, forma farmacéutica, concentración, vía, dosis, frecuencia, duración, cantidad total.
- Diagnóstico, fecha, firma.
- Sin enmendaduras.

> **Gap actual:** Fase 1 no exige sexo, peso pediátrico, vía de administración, ni forma farmacéutica como campo separado. Tampoco valida que se use DCI.

### 2.2 Receta especial (controlados)
- **Decreto Ley 22095** — Ley de represión del tráfico ilícito de drogas.
- **DS 023-2001-SA** — Reglamento de Estupefacientes, Psicotrópicos y Otras Sustancias Sujetas a Fiscalización Sanitaria.
- **RM 1105-2002-SA** — Recetarios especiales.

**Reglas duras del DS 023-2001-SA:**
- Listas IIA, IIIA, IIIB, IIIC → **recetario especial numerado** distribuido por MINSA, en papel autocopiativo (original + 2 copias).
- Listas IIB, IVA, IVB, VI → receta común.
- **Vigencia: 3 días** desde la emisión (Art. 23).
- Cantidad máxima:
  - Hospitalizado hiperalgésico: dosis de 24 h (Art. 26).
  - Ambulatorio hiperalgésico: hasta **15 días** de tratamiento.
- **3 ejemplares**: original + 1 copia al paciente, 1 copia para el prescriptor (retención 2 años).
- Datos del prescriptor obligatorios: nombre, **número de colegiatura, teléfono, dirección**.
- Datos del paciente: **nombre completo, dirección, teléfono, documento de identidad**.
- Diagnóstico, DCI, dosis, duración.
- Una vez dispensada, regente del establecimiento la firma, sella y folia.

> **Gap actual:** Fase 1 NO permite emitir recetas controladas. Necesitamos: numeración, validación de vigencia 3 días, validación de cantidad máxima 15 días para opioides, generación de las 3 copias, registro de qué médico está autorizado por DIGEMID.

### 2.3 Receta electrónica nacional
- **RM 079-2022-MINSA — Directiva 323-MINSA/DIGEMID-2022**.
- Estándar de transacción basado en **HL7** (mensajería). El detalle exacto de la directiva está en PDF escaneado y la implementación nacional es aún parcial — la integración con el repositorio único nacional **NO es obligatoria** para clínicas privadas hoy, pero la receta digital con firma electrónica **sí es válida** legalmente al amparo de la firma electrónica (IOFE / RENIEC) bajo Ley 27269.

> **Decisión:** Fase 2 no integra contra el repositorio nacional MINSA (no hay endpoint público abierto a privados todavía). En su lugar, generamos recetas electrónicas válidas con firma digital, identificador único, y QR de verificación que cubren el espíritu de la directiva 323 y permiten que cualquier farmacia las acepte. Cuando MINSA publique el endpoint, agregamos un adapter HL7-FHIR como Fase 3.

### 2.4 Firma digital
- **Ley 27269 — Firmas y Certificados Digitales** y su reglamento.
- La firma digital con valor legal en Perú se obtiene con certificado emitido por RENIEC (DNIe) o por una entidad acreditada bajo IOFE.
- Para el MVP, la firma digital nuestra **no usa certificado RENIEC** (eso requiere que cada médico tenga DNIe activo y la integración del lector de tarjeta/middleware en el navegador). Usamos firma simbólica + hash + QR de verificación, dejando como Fase 3 opcional la integración con el SDK de firma RENIEC.

---

## 3. Catálogo de fuentes investigadas (referencias rápidas)

| Fuente | Para qué se usa en Fase 2 |
|---|---|
| [DS 023-2001-SA — Reglamento de Estupefacientes](http://www.dirislimaeste.gob.pe/Virtual2/Otros_Link/DFCVS/D.S.%20N%C2%B0%20023-2001-SA%20-%20REGLAMENTO%20DE%20ESTUPEFACIENTES,%20PSICOTROPICOS.doc) | Reglas de receta especial, vigencia, cantidades máximas |
| [DIGEMID — Psicotrópicos y Estupefacientes](https://www.digemid.minsa.gob.pe/webDigemid/psicotropicos-y-estupefacientes/) | Listas de sustancias controladas, registro de prescriptores autorizados |
| [DS 014-2011-SA](https://www.digemid.minsa.gob.pe/webDigemid/normas-legales/2011/decreto-supremo-no-014-2011-sa/) | Reglamento de establecimientos farmacéuticos — datos mínimos de receta |
| [Manual de Buenas Prácticas de Prescripción (DIRESA Lima)](https://www.diresalima.gob.pe/diresa-antiguo/descargar/DIRECCION%20EJECUTIVA%20DE%20MEDICAMENTOS%20Y%20DROGAS/FISCALIZACION%20DE%20RECETAS%20MEDICAS/9.-MANUAL%20BUENAS%20PRACTICAS%20PRESCRIPCION.pdf) | Datos mínimos del prescriptor, paciente y medicamento |
| [PNUME — Petitorio Nacional Único de Medicamentos Esenciales](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2023/ANEXO_RM_633-2023-MINSA.pdf) | Lista oficial de DCIs esenciales — semilla del catálogo local |
| [RM 182-2025-MINSA](https://www.digemid.minsa.gob.pe/Archivos/Normatividad/2025/RM_182-2025-MINSA.pdf) | Anexo: medicamentos para HTA y DM2 — actualización del PNUME |
| [RM 393-2025-MINSA](https://www.digemid.minsa.gob.pe/webDigemid/normas-legales/2025/resolucion-ministerial-n-393-2025-minsa/) | Anexo: medicamentos de salud mental — actualización del PNUME |
| [Observatorio de Productos Farmacéuticos DIGEMID](https://opm-digemid.minsa.gob.pe/) | 16 000+ productos comerciales con DCI y precios — fuente para enriquecer el catálogo más allá del PNUME |
| [Consulta de Registro Sanitario DIGEMID](https://www.digemid.minsa.gob.pe/rsProductosFarmaceuticos/) | Verificación de productos con registro sanitario vigente |
| [RM 079-2022-MINSA — Directiva 323](https://www.digemid.minsa.gob.pe/webDigemid/normas-legales/2022/resolucion-ministerial-n-079-2022-minsa/) | Estándar HL7 de receta electrónica nacional (futuro adapter) |
| [Ley 27269 — Firmas y Certificados Digitales](https://www.gob.pe/institucion/reniec/normas-legales/firma-digital) | Marco legal para firma digital de la receta |
| [DrugBank Open Data (no comercial)](https://go.drugbank.com/releases/latest) | Base semilla de interacciones DDI — descarga académica |
| [RxNav (NIH) — APIs RxNorm](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html) | API gratis sin auth para normalizar nombres a RxCUI; el endpoint de interacciones fue **descontinuado en enero 2024**, así que solo lo usamos para nomenclatura |

> **Hallazgo importante sobre interacciones:** El servicio gratuito histórico (RxNav Drug Interaction API) se cerró en enero de 2024. La estrategia de Fase 2 es importar el dataset de DrugBank Open Data una sola vez y mantenerlo localmente. Es legalmente válido para uso clínico interno bajo su licencia académica/no-comercial; revisar términos antes de exponerlo como producto a terceros.

---

## 4. Componentes funcionales de Fase 2

Los 5 bloques pueden implementarse en este orden secuencial recomendado:

### Bloque A — Numeración correlativa por clínica
- Tabla `prescription_sequence` análoga a `lab_sequence`.
- Cada receta común recibe un número `RX-AAAA-NNNNNN` único por clínica al momento de **firmar** (no en draft).
- Las recetas controladas usan otra serie `RXC-AAAA-NNNNNN`.

### Bloque B — Catálogo DIGEMID local
- Tabla `medication_catalog` poblada vía seed con:
  - **DCI / IFA** (denominación común internacional) — campo principal de búsqueda.
  - Forma farmacéutica (tableta, cápsula, jarabe, ampolla, etc.) — enum.
  - Concentración (texto: "500 mg", "5 mg/ml").
  - Vía de administración (oral, IV, IM, tópica…) — enum.
  - Categoría ATC (opcional, para clasificación).
  - Lista controlada (`null` o `IIA`/`IIIA`/`IIIB`/`IIIC`/`IIB`/`IVA`/`IVB`/`VI`) — driver clave del flujo controlado.
  - `is_essential` boolean (PNUME).
  - `requires_special_recipe` boolean derivado de la lista.
- Source: PNUME 2024 (~1500 entradas) → primer seed; opcional: scrape del Observatorio para 16 000+ productos comerciales en una pasada offline.
- Endpoint `GET /api/v1/medications?q=&form=&controlled=` con búsqueda full-text en castellano (Postgres `tsvector`).
- En el frontend, el campo "Medicamento" del dialog cambia de Input libre a un Combobox con autocomplete remoto.

### Bloque C — Recetas controladas (psicotrópicos/estupefacientes)
- Modelo `Prescription` agrega columna `prescription_kind` enum: `common` | `controlled`.
- Validaciones (a nivel servicio + Pydantic):
  1. Si todos los items son del catálogo y ninguno es de listas IIA/IIIA/IIIB/IIIC → `common` (auto).
  2. Si al menos uno de los items es de lista controlada → forzar `kind=controlled` y exigir:
     - Diagnóstico **obligatorio** (no nulo).
     - **CIE-10 obligatorio**.
     - Datos completos del paciente (dirección + teléfono no nulos en `Patient`).
     - Médico marcado como `is_authorized_controlled` en `User` (campo nuevo, gestionado por admin de la clínica).
     - Duración total ≤ **15 días** para opioides (hiperalgésicos) — derivable de la lista.
- Plantilla PDF separada `controlled.html` que renderiza:
  - Encabezado "RECETA ESPECIAL — Sustancias controladas".
  - 3 ejemplares en una sola hoja A4 marcados "ORIGINAL — PACIENTE", "COPIA — PACIENTE", "COPIA — PRESCRIPTOR".
  - Datos completos del prescriptor (CMP, dirección, teléfono).
  - Datos completos del paciente (DNI, dirección, teléfono).
  - Cuadro de "Vigencia: 3 días desde la emisión" y `valid_until = created_at + 3 días` impreso visualmente.
  - Espacio para sello del regente farmacéutico al dispensar.
- Campo `valid_until` calculado y almacenado en BD para que la auditoría pueda detectar recetas vencidas.

### Bloque D — Alertas de interacciones medicamentosas (DDI)
- Tabla `drug_interaction` (medication_a_id, medication_b_id, severity enum: `minor`/`moderate`/`major`/`contraindicated`, description, source).
- Seed inicial desde **DrugBank Open Data** (descarga única, mapping a nuestro `medication_catalog` por DCI/RxCUI).
- Endpoint `POST /api/v1/medications/check-interactions` que recibe `[medication_id, medication_id, ...]` y devuelve la lista de pares con problema.
- En el frontend del dialog: cuando hay ≥2 items con `medication_id` resuelto, mostrar un panel naranja/rojo con las interacciones encontradas. **No bloqueante** — el médico puede ignorar y firmar igual, pero la alerta queda en el `audit_log` con `action=interaction_overridden`.
- También verificar contra **alergias del paciente** (campo `Patient.allergies` ya existente) — match por nombre del medicamento o por familia ATC si está disponible.

### Bloque E — QR de verificación pública
- Cada receta firmada genera:
  - `verification_code`: UUID corto (8 chars base32) almacenado en BD.
  - Hash SHA-256 del JSON canónico de la receta (paciente + items + firma + fecha).
- PDF incluye QR generado con `qrcode[pil]` apuntando a `https://{frontend}/verify/rx/{verification_code}`.
- Endpoint público nuevo `GET /api/v1/public/prescriptions/verify/{code}` (sin auth, rate-limited):
  - Devuelve: nombre de la clínica, fecha, nombre del médico, **estado** (`firmada` / `revocada` / `vencida`), hash, número de receta.
  - **No** devuelve datos del paciente ni medicamentos (privacidad).
- Página pública en frontend `/verify/rx/[code]` que muestra el resultado de manera clara para que un farmacéutico pueda verificar la autenticidad antes de dispensar.

### Bloque F (opcional, post Fase 2) — Adapter para receta electrónica nacional
- Cuando MINSA publique el endpoint del repositorio nacional, agregamos un servicio que convierte nuestra `Prescription` a mensaje HL7-FHIR según directiva 323 y la transmite. Por ahora se documenta como Fase 3.

---

## 5. Cambios de modelo de datos

### 5.1 Tablas/columnas nuevas

```text
medication_catalog
├── id (UUID, PK)
├── dci (text, indexed, full-text search)
├── pharmaceutical_form (enum: tablet, capsule, syrup, ampoule, ointment, …)
├── concentration (text, ej "500 mg")
├── route (enum: oral, iv, im, sc, topical, ophthalmic, …)
├── atc_code (text, nullable)
├── controlled_list (enum nullable: IIA, IIIA, IIIB, IIIC, IIB, IVA, IVB, VI)
├── is_essential (bool, default false)
├── requires_special_recipe (bool, computed/derived)
├── source (enum: pnume, oppf, manual)
├── created_at, updated_at
└── search_vector (tsvector, generated)
índice GIN sobre search_vector

drug_interaction
├── id (UUID, PK)
├── medication_a_id (FK medication_catalog)
├── medication_b_id (FK medication_catalog)
├── severity (enum: minor, moderate, major, contraindicated)
├── description (text)
├── source (text, ej "drugbank-open-2026-01")
└── UNIQUE (medication_a_id, medication_b_id) con LEAST/GREATEST

prescription_sequence
├── id (UUID, PK)
├── clinic_id (FK)
├── kind (enum: common, controlled)
├── year (int)
├── current_number (int)
└── UNIQUE (clinic_id, kind, year)
```

### 5.2 Modificaciones a tablas existentes

```text
prescriptions
+ kind (enum: common, controlled, default common)
+ serial_number (text, nullable hasta firma; ej "RX-2026-000123")
+ verification_code (text, unique, generado al firmar)
+ content_hash (text, SHA-256 al firmar)
+ valid_until (date, calculado para controladas)

prescription_items
+ medication_id (FK medication_catalog, nullable para retrocompatibilidad)
+ pharmaceutical_form (text)  ← derivado del catálogo, congelado al firmar
+ route (text)                ← idem

users
+ is_authorized_controlled (bool, default false)
+ controlled_authorization_number (text, nullable)  ← número emitido por DIGEMID

patients
(sin cambios — los campos address y phone_number ya existen pero deben validarse no-null al emitir receta controlada)
```

### 5.3 Migración Alembic

Una sola migración con id `j2f3a4b5c6d7_phase2_prescriptions.py` que:
1. Crea las 3 tablas nuevas.
2. Añade las columnas a `prescriptions`, `prescription_items` y `users`.
3. Crea el índice GIN sobre `medication_catalog.search_vector` y un trigger para mantenerlo.
4. Crea índices `idx_drug_interaction_pair` y `idx_prescription_serial`.

---

## 6. Cambios en backend

### 6.1 Archivos nuevos
- `app/models/medication_catalog.py`
- `app/models/drug_interaction.py`
- `app/models/prescription_sequence.py`
- `app/schemas/medication_catalog.py`
- `app/schemas/drug_interaction.py`
- `app/services/medication_catalog_service.py`
- `app/services/drug_interaction_service.py`
- `app/services/prescription_sequence_service.py`
- `app/api/v1/medications.py` — endpoints públicos del catálogo y DDI checker
- `app/api/v1/public_prescriptions.py` — endpoint público de verificación QR
- `app/templates/prescriptions/controlled.html` — plantilla del recetario especial
- `app/seeds/pnume_2024.json` — semilla del catálogo (extracto del PNUME)
- `app/seeds/drugbank_interactions.json` — semilla DDI procesada
- `app/scripts/seed_medication_catalog.py` — comando para repoblar el catálogo
- `app/scripts/import_drugbank.py` — script one-shot que toma el dump XML de DrugBank Open Data y produce el JSON

### 6.2 Archivos modificados
- `app/models/prescription.py` — añadir kind, serial_number, verification_code, content_hash, valid_until + relación con `medication_catalog` en items.
- `app/models/user.py` — flags de autorización para controlados.
- `app/services/prescription_service.py` — toda la lógica nueva: detección automática de kind, validaciones de receta controlada, generación del serial al firmar, hash, verification_code, llamadas al DDI checker.
- `app/services/pdf_service.py` — render condicional `controlled.html` vs `prescription.html` según `kind`; insertar QR; renderizar 3 ejemplares en una hoja para controladas.
- `app/api/v1/prescriptions.py` — exponer el endpoint `POST /{rx_id}/check-interactions` para previsualizar antes de firmar.
- `app/api/v1/router.py` — registrar `medications_router` y `public_prescriptions_router`.

### 6.3 Dependencias nuevas en `requirements.txt`
```
qrcode[pil]>=7.4
```
(El catálogo PNUME y DrugBank se manejan offline con scripts; no necesitan librerías nuevas.)

---

## 7. Cambios en frontend

### 7.1 Tipos nuevos en `types/index.ts`
```ts
type ControlledList = "IIA" | "IIIA" | "IIIB" | "IIIC" | "IIB" | "IVA" | "IVB" | "VI" | null;
type PharmaceuticalForm = "tablet" | "capsule" | "syrup" | "ampoule" | "ointment" | ...;

interface Medication {
  id: string;
  dci: string;
  pharmaceutical_form: PharmaceuticalForm;
  concentration: string;
  route: string;
  controlled_list: ControlledList;
  requires_special_recipe: boolean;
  is_essential: boolean;
}

interface DrugInteraction {
  medication_a: { id: string; dci: string };
  medication_b: { id: string; dci: string };
  severity: "minor" | "moderate" | "major" | "contraindicated";
  description: string;
}
```

Y extender `PrescriptionItem` con `medication_id`, `pharmaceutical_form`, `route`. Extender `Prescription` con `kind`, `serial_number`, `verification_code`, `valid_until`.

### 7.2 Hooks nuevos
- `use-medication-catalog.ts` — `searchMedications(q)`, `getMedication(id)`.
- `use-drug-interactions.ts` — `checkInteractions(medication_ids[])`.

### 7.3 Componentes nuevos
- `medication-combobox.tsx` — Combobox shadcn con autocomplete remoto debounced (300 ms) que reemplaza el Input libre del item del dialog. Muestra DCI + concentración + forma + badge "controlado" cuando aplica.
- `interaction-alert.tsx` — Panel naranja/rojo dentro del dialog cuando hay interacciones, con severidad y descripción por par.
- `prescription-controlled-warning.tsx` — Banner que aparece cuando la receta se vuelve "controlled" automáticamente, recordando los requisitos extra (CMP, dirección del paciente, etc.).
- `app/(public)/verify/rx/[code]/page.tsx` — Página pública sin layout dashboard para verificación QR.

### 7.4 Componentes modificados
- `prescription-dialog.tsx`:
  - Reemplaza Input de medicamento por `<MedicationCombobox />`.
  - Cuando cualquier item resuelve a una medicación con `controlled_list != null`, dispara modo controlado: bloquea submit si faltan datos del paciente; añade banner.
  - Polling al endpoint de DDI cada vez que cambia la lista de items resueltos; renderiza `<InteractionAlert />`.
- `prescriptions-table.tsx`:
  - Muestra `serial_number` cuando existe.
  - Badge naranja "Controlada" para `kind=controlled`.
  - Badge rojo "Vencida" cuando `valid_until < hoy` y no fue dispensada.

---

## 8. Plan de implementación por hitos

Cada hito es independientemente desplegable y verificable. El orden está optimizado para entregar valor temprano y reducir el riesgo de regresiones.

### Hito 2.1 — Numeración correlativa (1 día)
**Objetivo:** Cada receta firmada lleva un número único por clínica.
1. Crear modelo + migración `prescription_sequence`.
2. Crear `prescription_sequence_service.next_serial(clinic_id, kind)` con `SELECT … FOR UPDATE`.
3. En `sign_prescription`: calcular serial antes de marcar `signed_at`.
4. PDF: imprimir el serial en el encabezado.
5. Frontend: mostrar serial en tabla y dialog.

**Verificación:** 100 firmas paralelas con script asyncio → 100 seriales únicos consecutivos.

### Hito 2.2 — Catálogo DIGEMID (3-4 días)
**Objetivo:** Sustituir el campo libre de medicamento por catálogo con autocomplete.
1. Modelo + migración `medication_catalog` con `tsvector` + trigger.
2. Script `seed_medication_catalog.py` que carga el JSON del PNUME 2024 (~1500 entradas).
3. Endpoint `GET /api/v1/medications?q=&controlled=&form=` con paginación.
4. Hook `use-medication-catalog` y componente `medication-combobox`.
5. Modificar `prescription-dialog.tsx`: el Input medicamento → Combobox. Permitir aún texto libre como fallback (campo `custom_medication`) para casos no catalogados.
6. `prescription_items.medication_id` opcional pero recomendado.

**Verificación:** Buscar "amox" devuelve "Amoxicilina (oral, tableta, 500 mg)" y "Amoxicilina + Ácido clavulánico" en <100 ms con 1500 registros.

### Hito 2.3 — Recetas controladas (3-4 días)
**Objetivo:** Permitir emitir psicotrópicos/estupefacientes con flujo regulado.
1. Migración: `prescriptions.kind`, `valid_until`, `User.is_authorized_controlled`.
2. Marcar en el seed las DCIs controladas con su lista (IIA/IIIA-C) según anexos del DS 023-2001-SA. (El listado vive en `app/seeds/controlled_substances.json`.)
3. En `prescription_service.create/update`:
   - Detectar `kind` automáticamente.
   - Validar requisitos extra para `controlled`.
4. Crear `templates/prescriptions/controlled.html` con 3 ejemplares por hoja.
5. `pdf_service.render_prescription_pdf` selecciona plantilla por kind.
6. Frontend: banner + bloqueos.
7. Sección en configuración de clínica para que admin marque qué doctores tienen `is_authorized_controlled = true`.

**Verificación:** Crear una receta con Tramadol (lista IIIA) sin dirección del paciente → 422 con error claro. Con dirección → 201, PDF con 3 ejemplares y "Vigencia: 3 días".

### Hito 2.4 — Detector de interacciones (3-4 días)
**Objetivo:** Alertar antes de firmar recetas con combinaciones peligrosas.
1. Migración: tabla `drug_interaction`.
2. Script `import_drugbank.py` (proceso manual one-shot fuera del runtime; entrega un JSON grande). Operador corre el script una vez, commit del JSON resultante. **Validar términos de licencia DrugBank Open Data antes de incluir el JSON en el repo.** Alternativa segura: dejar el archivo fuera de git y proveerlo como asset descargable durante el deploy.
3. Endpoint `POST /api/v1/medications/check-interactions`.
4. Hook + componente `interaction-alert.tsx`.
5. En el dialog: cada vez que cambia la lista de items resueltos a `medication_id`, llamar al checker (debounced 500 ms).
6. Permitir submit con un confirm "¿Confirmar a pesar de la interacción?" que se loguea en `audit_log`.
7. Validar contra `Patient.allergies` (string libre): match case-insensitive contra `medication.dci`.

**Verificación:** Crear receta con Tramadol + Sertralina → alerta "MAYOR — riesgo de síndrome serotoninérgico". Override → registro en audit log con `action=interaction_overridden`.

### Hito 2.5 — QR de verificación pública (2 días)
**Objetivo:** Que cualquier farmacéutico verifique la autenticidad escaneando un QR.
1. Migración: añadir `verification_code`, `content_hash`.
2. En `sign_prescription`:
   - Generar `verification_code` (8 chars base32 sobre UUID4).
   - Computar `content_hash = sha256(canonical_json(rx))`.
3. Endpoint público `GET /api/v1/public/prescriptions/verify/{code}` (sin auth, rate limit por IP via slowapi: 30 req/min).
4. Página pública `/verify/rx/[code]` en frontend.
5. PDF: insertar QR en pie de página apuntando a `https://{frontend_url}/verify/rx/{code}`. Usar `qrcode[pil]` y embebido como imagen base64.

**Verificación:** Escanear QR de un PDF firmado abre la página de verificación con datos correctos. Un código alterado retorna 404. El hash mostrado coincide con el del PDF.

### Total estimado
~13-15 días de trabajo enfocado, distribuibles en 2-3 sprints.

---

## 9. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El JSON de DrugBank Open Data viola términos al redistribuirse en el repo | Media | Legal/operativo | No comitear el JSON; el operador del deploy lo descarga desde DrugBank y lo coloca como volumen. Documentarlo en `DEPLOY.md`. |
| Las clínicas no quieren capacitar a sus médicos en el flujo de controladas | Media | Adopción | Feature flag por clínica `controlled_prescriptions_enabled`. Si está apagado, el dialog ni siquiera muestra los medicamentos controlados en el combobox. |
| El catálogo PNUME tiene <2000 entradas y los médicos buscan productos comerciales | Alta | UX | Permitir texto libre como fallback (`custom_medication`). Considerar enriquecer el catálogo con un scrape one-shot del Observatorio (16 000+ productos) cuando sea necesario. |
| El médico marcado como "autorizado controlados" en realidad no tiene autorización vigente de DIGEMID | Media | Legal | El admin de clínica es responsable de mantener `is_authorized_controlled` actualizado. Auditoría en `audit_log` de cada cambio. Contemplar campo `controlled_authorization_expiry`. |
| MINSA publica de golpe el endpoint nacional y nos exige integrar | Baja | Cronograma | El bloque F (adapter HL7-FHIR) está aislado; podemos agregarlo sin tocar el modelo de datos. |
| Falsos positivos en interacciones generan ruido y los médicos las ignoran sistemáticamente | Media | Adopción | Severidad mínima por defecto = `moderate`; las `minor` no se muestran como alerta sino como nota informativa. |
| Hash de la receta cambia si reordenan items o renombran campos | Alta | Verificación | Definir un canonicalizador estricto (orden alfabético, encoding fijo) y testearlo unitariamente con golden files. |

---

## 10. Tests recomendados

Backend:
- `test_prescription_sequence.py` — concurrencia: 50 firmas paralelas → 50 seriales únicos.
- `test_medication_catalog_search.py` — fuzzy search en español con tildes.
- `test_controlled_validation.py` — receta con tramadol sin dirección del paciente → 422; con todos los datos → 201.
- `test_interaction_check.py` — golden test contra un set de pares conocidos.
- `test_verification_endpoint.py` — código válido → 200 con datos públicos; código inválido → 404; rate limit a partir de la 31ª request en 1 min.
- `test_pdf_controlled_template.py` — render del PDF, validar que aparezcan las 3 etiquetas "ORIGINAL/COPIA/COPIA".
- `test_canonical_hash.py` — golden file: el hash es estable tras serializar/deserializar la misma receta 100 veces.

Frontend:
- Smoke test en la página de recetas: crear receta común con 2 items del catálogo → no hay alerta.
- Smoke test: agregar Tramadol + Sertralina → aparece banner DDI mayor.
- Smoke test: agregar Diazepam (lista IIIB) → banner controlada y submit bloqueado si paciente no tiene dirección.
- Test E2E mínimo: firmar una receta común → descargar PDF → escanear QR (manual) → verificar página pública.

---

## 11. Decisiones que requieren confirmación del cliente antes de empezar

1. **Catálogo:** ¿Empezamos solo con PNUME (~1500 DCIs esenciales) o invertimos esfuerzo extra en el scrape del Observatorio (16 000+ productos comerciales)?
   - **Recomendación:** PNUME en Hito 2.2; scrape del Observatorio diferido a un Hito 2.2.b solo si los médicos lo piden.
2. **DrugBank:** ¿Aceptamos los términos de DrugBank Open Data (no comercial, atribución obligatoria) o preferimos construir manualmente una tabla pequeña de las 50-100 interacciones más críticas en gineco-obstetricia?
   - **Recomendación:** Tabla manual pequeña de alta calidad para evitar ruido de falsos positivos y cualquier duda legal. DrugBank queda como upgrade futuro.
3. **Firma RENIEC:** ¿El cliente exige firma con certificado DNIe (requiere lectores físicos en cada consultorio) o le basta con firma simbólica + QR + hash?
   - **Recomendación:** QR + hash en Fase 2; integración RENIEC se evalúa en Fase 3 cuando haya un caso de uso real (auditoría legal externa).
4. **Recetas controladas:** ¿La clínica del cliente realmente prescribe psicotrópicos/estupefacientes con frecuencia, o este bloque puede esperar?
   - **Recomendación:** Si la clínica es gineco-obstétrica pura, los controlados son ocasionales (Tramadol post-cesárea, Diazepam ansiolítico). El Hito 2.3 vale la pena igual porque es un diferenciador comercial frente a competidores.
5. **Numeración:** ¿La clínica ya usa una numeración manual de talonario que necesitamos respetar como punto de partida (offset)?
   - **Recomendación:** Permitir configurar el `current_number` inicial por clínica desde la UI de Configuración.

---

## 12. Definición de "hecho" para Fase 2

La Fase 2 se considera completa cuando:

- [x] Toda migración corre limpia en BD vacía y en BD con datos reales de Fase 1.
- [x] El catálogo PNUME está sembrado y se puede buscar.
- [x] Una receta con un opioide se rechaza si falta dirección del paciente.
- [x] El PDF de receta controlada imprime los 3 ejemplares y la vigencia visible.
- [x] El detector DDI muestra alerta para al menos 3 pares clínicamente relevantes (Tramadol+Sertralina, Warfarina+AINEs, Carbamazepina+Anticonceptivos orales).
- [x] El QR del PDF abre la página pública y muestra estado correcto.
- [x] Los tests del bloque pasan en CI.
- [x] El frontend compila sin warnings nuevos en `npm run build`.
- [x] La documentación de operación (`DEPLOY.md`) explica cómo cargar el catálogo y el JSON DDI en producción.

---

**Fin del plan.**
