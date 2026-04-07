"""Add signature columns to imaging_reports

Revision ID: g9c0d1e2f3a4
Revises: f8b9c0d1e2f3
Create Date: 2026-04-06

Fase 5 — Firma digital de informes de imagenología.
Una vez firmado (signed_at != NULL), el informe se vuelve INMUTABLE
(no puede editarse ni eliminarse). Solo el doctor que creó el informe
puede firmarlo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "g9c0d1e2f3a4"
down_revision: Union[str, None] = "f8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "imaging_reports",
        sa.Column(
            "signed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Fecha y hora de firma digital. Si != NULL el informe es inmutable.",
        ),
    )
    op.add_column(
        "imaging_reports",
        sa.Column(
            "signed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="Doctor que firmó el informe (debe ser el mismo que doctor_id).",
        ),
    )
    op.create_index(
        "idx_imaging_signed",
        "imaging_reports",
        ["clinic_id", "signed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_imaging_signed", table_name="imaging_reports")
    op.drop_column("imaging_reports", "signed_by")
    op.drop_column("imaging_reports", "signed_at")
