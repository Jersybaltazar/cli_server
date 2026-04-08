"""Create prescriptions and prescription_items tables

Revision ID: i1e2f3a4b5c6
Revises: h0d1e2f3a4b5
Create Date: 2026-04-07

Recetas médicas comunes (Fase 1) — encabezado y líneas de medicamentos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "i1e2f3a4b5c6"
down_revision: Union[str, None] = "h0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prescriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("record_id", UUID(as_uuid=True), sa.ForeignKey("medical_records.id"), nullable=True),
        sa.Column("diagnosis", sa.Text, nullable=True),
        sa.Column("cie10_code", sa.String(10), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_prescription_clinic_patient",
        "prescriptions",
        ["clinic_id", "patient_id"],
    )
    op.create_index(
        "idx_prescription_created",
        "prescriptions",
        ["clinic_id", "created_at"],
    )
    op.create_index(
        "idx_prescription_signed",
        "prescriptions",
        ["clinic_id", "signed_at"],
    )

    op.create_table(
        "prescription_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "prescription_id",
            UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("medication", sa.String(255), nullable=False),
        sa.Column("presentation", sa.String(120), nullable=True),
        sa.Column("dose", sa.String(120), nullable=True),
        sa.Column("frequency", sa.String(120), nullable=True),
        sa.Column("duration", sa.String(120), nullable=True),
        sa.Column("quantity", sa.String(60), nullable=True),
        sa.Column("instructions", sa.Text, nullable=True),
    )
    op.create_index(
        "idx_prescription_item_rx",
        "prescription_items",
        ["prescription_id"],
    )

    # ── Plantillas reutilizables de recetas (recetas frecuentes) ──
    op.create_table(
        "prescription_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("diagnosis", sa.Text, nullable=True),
        sa.Column("cie10_code", sa.String(10), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("items", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_prescription_tpl_clinic",
        "prescription_templates",
        ["clinic_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_prescription_tpl_clinic", table_name="prescription_templates")
    op.drop_table("prescription_templates")
    op.drop_index("idx_prescription_item_rx", table_name="prescription_items")
    op.drop_table("prescription_items")
    op.drop_index("idx_prescription_signed", table_name="prescriptions")
    op.drop_index("idx_prescription_created", table_name="prescriptions")
    op.drop_index("idx_prescription_clinic_patient", table_name="prescriptions")
    op.drop_table("prescriptions")
