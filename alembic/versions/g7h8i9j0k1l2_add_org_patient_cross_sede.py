"""Add organization_id, org_dni_hash to patients + patient_clinic_links table

Soporta pacientes compartidos entre sedes de una misma organización.
- patients.organization_id: vincula paciente a la organización
- patients.org_dni_hash: SHA-256 de org_id+dni para dedup cross-sede
- patient_clinic_links: registra en qué sedes está registrado un paciente

Revision ID: g7h8i9j0k1l2
Revises: 4c8845aab862
Create Date: 2026-02-16

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "4c8845aab862"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Agregar columnas a patients ────────────────
    op.add_column(
        "patients",
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=True,
            comment="Organización a la que pertenece (null = clínica independiente)",
        ),
    )
    op.create_index("idx_patient_organization", "patients", ["organization_id"])

    op.add_column(
        "patients",
        sa.Column(
            "org_dni_hash",
            sa.String(64),
            nullable=True,
            comment="SHA-256 de org_id+dni para dedup cross-sede",
        ),
    )

    # ── 2. Crear tabla patient_clinic_links ────────────
    op.create_table(
        "patient_clinic_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("registered_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("patient_id", "clinic_id", name="uq_patient_clinic_link"),
    )

    # ── 3. Data migration: popular organization_id y org_dni_hash ──
    # Esto se ejecuta en SQL puro para organization_id (no requiere descifrar)
    # El org_dni_hash requiere descifrar el DNI, así que se hace en Python
    # después de ejecutar esta migración, via script separado.
    #
    # Seteamos organization_id desde la clínica del paciente:
    op.execute(
        text("""
            UPDATE patients p
            SET organization_id = c.organization_id
            FROM clinics c
            WHERE p.clinic_id = c.id
            AND c.organization_id IS NOT NULL
        """)
    )

    # ── 4. Popular patient_clinic_links con datos existentes ──
    op.execute(
        text("""
            INSERT INTO patient_clinic_links (id, patient_id, clinic_id, registered_at)
            SELECT gen_random_uuid(), p.id, p.clinic_id, p.created_at
            FROM patients p
            ON CONFLICT (patient_id, clinic_id) DO NOTHING
        """)
    )

    # ── 5. Crear índice unique parcial para org_dni_hash ──
    # (solo donde no es null, para permitir nulls en clínicas independientes)
    op.execute(
        text("""
            CREATE UNIQUE INDEX idx_patient_org_dni_hash
            ON patients (org_dni_hash)
            WHERE org_dni_hash IS NOT NULL
        """)
    )


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS idx_patient_org_dni_hash"))
    op.drop_table("patient_clinic_links")
    op.drop_index("idx_patient_organization", table_name="patients")
    op.drop_column("patients", "org_dni_hash")
    op.drop_column("patients", "organization_id")
