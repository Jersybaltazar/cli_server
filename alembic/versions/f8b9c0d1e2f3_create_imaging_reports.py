"""Create imaging_reports table

Revision ID: f8b9c0d1e2f3
Revises: e5a6b7c8d9e0
Create Date: 2026-04-06

Crea la tabla imaging_reports para almacenar informes estructurados de
ecografías y procedimientos (pélvica, transvaginal, obstétrica, Doppler,
morfológica, genética, mamas, histerosonografía, colposcopia, etc.).

- Una sola tabla con discriminador study_type (enum)
- Campo findings (JSONB) con estructura específica por tipo
- Campo conclusion_items (JSONB) con lista de ítems
- Vínculo opcional con medical_records para firma digital e inmutabilidad
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "f8b9c0d1e2f3"
down_revision: Union[str, None] = "e5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Cleanup seguro (idempotente) ─────────────────
    op.execute("DROP TABLE IF EXISTS imaging_reports CASCADE")
    op.execute("DROP TYPE IF EXISTS imagingstudytype CASCADE")

    # ── 1. Crear enum ────────────────────────────────
    op.execute(
        "CREATE TYPE imagingstudytype AS ENUM ("
        "'pelvic', 'transvaginal', 'obstetric_first', 'obstetric_second_third', "
        "'obstetric_doppler', 'obstetric_twin', 'obstetric_twin_doppler', "
        "'breast', 'morphologic', 'genetic', 'hysterosonography', 'colposcopy'"
        ")"
    )

    imagingstudytype_enum = postgresql.ENUM(
        "pelvic",
        "transvaginal",
        "obstetric_first",
        "obstetric_second_third",
        "obstetric_doppler",
        "obstetric_twin",
        "obstetric_twin_doppler",
        "breast",
        "morphologic",
        "genetic",
        "hysterosonography",
        "colposcopy",
        name="imagingstudytype",
        create_type=False,
    )

    # ── 2. imaging_reports ───────────────────────────
    op.create_table(
        "imaging_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("record_id", UUID(as_uuid=True), sa.ForeignKey("medical_records.id"), nullable=True),
        sa.Column("study_type", imagingstudytype_enum, nullable=False),
        sa.Column("findings", JSONB, nullable=False, server_default="{}"),
        sa.Column("conclusion_items", JSONB, nullable=False, server_default="[]"),
        sa.Column("recommendations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_imaging_clinic_patient",
        "imaging_reports",
        ["clinic_id", "patient_id"],
    )
    op.create_index(
        "idx_imaging_study_type",
        "imaging_reports",
        ["clinic_id", "study_type"],
    )
    op.create_index(
        "idx_imaging_created",
        "imaging_reports",
        ["clinic_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_imaging_created", table_name="imaging_reports")
    op.drop_index("idx_imaging_study_type", table_name="imaging_reports")
    op.drop_index("idx_imaging_clinic_patient", table_name="imaging_reports")
    op.drop_table("imaging_reports")
    op.execute("DROP TYPE IF EXISTS imagingstudytype CASCADE")
