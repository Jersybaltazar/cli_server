-- ============================================================
-- Script de configuración de Row-Level Security (RLS)
-- Ejecutar DESPUÉS de la migración inicial de Alembic.
-- ============================================================

-- ── Habilitar RLS en tablas con clinic_id ──────────

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctor_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE dental_charts ENABLE ROW LEVEL SECURITY;
ALTER TABLE prenatal_visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE ophthalmic_exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_device_mappings ENABLE ROW LEVEL SECURITY;

-- ── Políticas de aislamiento por clínica ───────────

-- Users: solo ver usuarios de tu clínica
CREATE POLICY users_clinic_isolation ON users
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Patients: solo ver pacientes de tu clínica
CREATE POLICY patients_clinic_isolation ON patients
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Audit Log: solo ver logs de tu clínica
CREATE POLICY audit_log_clinic_isolation ON audit_log
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Appointments: solo ver citas de tu clínica
CREATE POLICY appointments_clinic_isolation ON appointments
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Doctor Schedules: solo ver horarios de tu clínica
CREATE POLICY doctor_schedules_clinic_isolation ON doctor_schedules
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Medical Records: solo ver registros de tu clínica
CREATE POLICY medical_records_clinic_isolation ON medical_records
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Dental Charts: solo ver odontogramas de tu clínica
CREATE POLICY dental_charts_clinic_isolation ON dental_charts
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Prenatal Visits: solo ver controles prenatales de tu clínica
CREATE POLICY prenatal_visits_clinic_isolation ON prenatal_visits
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Ophthalmic Exams: solo ver exámenes de tu clínica
CREATE POLICY ophthalmic_exams_clinic_isolation ON ophthalmic_exams
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Invoices: solo ver comprobantes de tu clínica
CREATE POLICY invoices_clinic_isolation ON invoices
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Sync Queue: solo ver batches de sync de tu clínica
CREATE POLICY sync_queue_clinic_isolation ON sync_queue
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- Sync Device Mappings: solo ver mapeos de tu clínica
CREATE POLICY sync_device_mappings_clinic_isolation ON sync_device_mappings
    USING (clinic_id = current_setting('app.clinic_id')::uuid);

-- ── Proteger audit_log contra UPDATE/DELETE ────────

-- Revocar UPDATE y DELETE en audit_log para el rol de la app
-- (ajustar 'app_user' al rol de PostgreSQL que usa la aplicación)
-- REVOKE UPDATE, DELETE ON audit_log FROM app_user;

-- ── Índices adicionales para performance ───────────

CREATE INDEX IF NOT EXISTS idx_patients_clinic_active
    ON patients (clinic_id, is_active);

CREATE INDEX IF NOT EXISTS idx_patients_dni_hash
    ON patients (dni_hash);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity_action
    ON audit_log (clinic_id, entity, action, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_users_clinic_role
    ON users (clinic_id, role);

-- ============================================================
-- NOTA: Para tablas futuras (medical_records, invoices, etc.),
-- repetir el patrón:
--   ALTER TABLE <tabla> ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY <tabla>_clinic_isolation ON <tabla>
--       USING (clinic_id = current_setting('app.clinic_id')::uuid);
-- ============================================================
