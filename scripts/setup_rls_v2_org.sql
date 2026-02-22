-- ============================================================
-- RLS v2 — Políticas cross-sede para organizaciones
--
-- Ejecutar DESPUÉS de:
--   1. La migración g7h8i9j0k1l2 (campos org en patients)
--   2. El script setup_rls.sql original
--
-- Tablas modificadas: patients, medical_records, appointments
-- Tablas SIN cambio: invoices, cash_sessions, cash_movements,
--   inventory_items, stock_movements, suppliers, services,
--   doctor_schedules, audit_log, sync_queue
-- ============================================================

-- ── Habilitar RLS en patient_clinic_links ────────────

ALTER TABLE patient_clinic_links ENABLE ROW LEVEL SECURITY;

-- patient_clinic_links: lectura libre (la autorización la maneja la app)
-- Escritura solo si clinic_id coincide con la sede actual
CREATE POLICY pcl_read ON patient_clinic_links
    FOR SELECT USING (true);

CREATE POLICY pcl_write ON patient_clinic_links
    FOR INSERT WITH CHECK (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- ── Habilitar RLS en cash_sessions y cash_movements ──

ALTER TABLE cash_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_movements ENABLE ROW LEVEL SECURITY;

CREATE POLICY cash_sessions_clinic_isolation ON cash_sessions
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

CREATE POLICY cash_movements_clinic_isolation ON cash_movements
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- ============================================================
-- PATIENTS — SELECT cross-sede, escritura solo sede actual
-- ============================================================

-- Eliminar política anterior
DROP POLICY IF EXISTS patients_clinic_isolation ON patients;

-- SELECT: permitir si es tu sede O si pertenece a la misma organización
CREATE POLICY patients_org_read ON patients
    FOR SELECT USING (
        clinic_id = current_setting('app.clinic_id')::uuid
        OR (
            organization_id IS NOT NULL
            AND organization_id IN (
                SELECT organization_id FROM clinics
                WHERE id = current_setting('app.clinic_id')::uuid
                AND organization_id IS NOT NULL
            )
        )
    );

-- INSERT: solo en tu sede
CREATE POLICY patients_clinic_insert ON patients
    FOR INSERT WITH CHECK (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- UPDATE: solo pacientes de tu sede
CREATE POLICY patients_clinic_update ON patients
    FOR UPDATE USING (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- ============================================================
-- MEDICAL_RECORDS — SELECT cross-sede, escritura solo sede actual
-- ============================================================

DROP POLICY IF EXISTS medical_records_clinic_isolation ON medical_records;

-- SELECT: permitir lectura cross-sede dentro de la misma org
CREATE POLICY medical_records_org_read ON medical_records
    FOR SELECT USING (
        clinic_id = current_setting('app.clinic_id')::uuid
        OR clinic_id IN (
            SELECT c2.id FROM clinics c1
            JOIN clinics c2 ON c1.organization_id = c2.organization_id
            WHERE c1.id = current_setting('app.clinic_id')::uuid
            AND c1.organization_id IS NOT NULL
        )
    );

-- INSERT: solo en tu sede (el doctor crea el registro en su sede)
CREATE POLICY medical_records_clinic_insert ON medical_records
    FOR INSERT WITH CHECK (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- UPDATE: solo registros de tu sede (para firma)
CREATE POLICY medical_records_clinic_update ON medical_records
    FOR UPDATE USING (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- ============================================================
-- APPOINTMENTS — SELECT cross-sede, escritura solo sede actual
-- ============================================================

DROP POLICY IF EXISTS appointments_clinic_isolation ON appointments;

-- SELECT: permitir lectura cross-sede dentro de la misma org
CREATE POLICY appointments_org_read ON appointments
    FOR SELECT USING (
        clinic_id = current_setting('app.clinic_id')::uuid
        OR clinic_id IN (
            SELECT c2.id FROM clinics c1
            JOIN clinics c2 ON c1.organization_id = c2.organization_id
            WHERE c1.id = current_setting('app.clinic_id')::uuid
            AND c1.organization_id IS NOT NULL
        )
    );

-- INSERT: solo en tu sede
CREATE POLICY appointments_clinic_insert ON appointments
    FOR INSERT WITH CHECK (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- UPDATE: solo citas de tu sede
CREATE POLICY appointments_clinic_update ON appointments
    FOR UPDATE USING (
        clinic_id = current_setting('app.clinic_id')::uuid
    );

-- ============================================================
-- Tablas de especialidad — misma lógica cross-sede para SELECT
-- ============================================================

DROP POLICY IF EXISTS dental_charts_clinic_isolation ON dental_charts;
CREATE POLICY dental_charts_org_read ON dental_charts
    FOR SELECT USING (
        clinic_id = current_setting('app.clinic_id')::uuid
        OR clinic_id IN (
            SELECT c2.id FROM clinics c1
            JOIN clinics c2 ON c1.organization_id = c2.organization_id
            WHERE c1.id = current_setting('app.clinic_id')::uuid
            AND c1.organization_id IS NOT NULL
        )
    );
CREATE POLICY dental_charts_clinic_write ON dental_charts
    FOR INSERT WITH CHECK (clinic_id = current_setting('app.clinic_id')::uuid);
CREATE POLICY dental_charts_clinic_update ON dental_charts
    FOR UPDATE USING (clinic_id = current_setting('app.clinic_id')::uuid);

DROP POLICY IF EXISTS prenatal_visits_clinic_isolation ON prenatal_visits;
CREATE POLICY prenatal_visits_org_read ON prenatal_visits
    FOR SELECT USING (
        clinic_id = current_setting('app.clinic_id')::uuid
        OR clinic_id IN (
            SELECT c2.id FROM clinics c1
            JOIN clinics c2 ON c1.organization_id = c2.organization_id
            WHERE c1.id = current_setting('app.clinic_id')::uuid
            AND c1.organization_id IS NOT NULL
        )
    );
CREATE POLICY prenatal_visits_clinic_write ON prenatal_visits
    FOR INSERT WITH CHECK (clinic_id = current_setting('app.clinic_id')::uuid);
CREATE POLICY prenatal_visits_clinic_update ON prenatal_visits
    FOR UPDATE USING (clinic_id = current_setting('app.clinic_id')::uuid);

DROP POLICY IF EXISTS ophthalmic_exams_clinic_isolation ON ophthalmic_exams;
CREATE POLICY ophthalmic_exams_org_read ON ophthalmic_exams
    FOR SELECT USING (
        clinic_id = current_setting('app.clinic_id')::uuid
        OR clinic_id IN (
            SELECT c2.id FROM clinics c1
            JOIN clinics c2 ON c1.organization_id = c2.organization_id
            WHERE c1.id = current_setting('app.clinic_id')::uuid
            AND c1.organization_id IS NOT NULL
        )
    );
CREATE POLICY ophthalmic_exams_clinic_write ON ophthalmic_exams
    FOR INSERT WITH CHECK (clinic_id = current_setting('app.clinic_id')::uuid);
CREATE POLICY ophthalmic_exams_clinic_update ON ophthalmic_exams
    FOR UPDATE USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- ============================================================
-- NOTA: Las siguientes tablas mantienen aislamiento estricto
-- por sede (sin cross-sede):
--   users, audit_log, doctor_schedules, invoices,
--   cash_sessions, cash_movements, sync_queue, sync_device_mappings
-- ============================================================
