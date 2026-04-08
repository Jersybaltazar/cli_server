"""Add prescription sequence + serial_number column

Revision ID: j2f3a4b5c6d7
Revises: i1e2f3a4b5c6
Create Date: 2026-04-08

Fase 2 — Hito 2.1: numeración correlativa por clínica.
Formato: RX-AAAA-NNNNNN (recetas comunes), RXC-AAAA-NNNNNN (controladas, Fase 2.3).
El serial se asigna al firmar (no en draft) para evitar huecos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "j2f3a4b5c6d7"
down_revision: Union[str, None] = "i1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prescription_sequences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id", UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"), nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("last_number", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "clinic_id", "kind", "year",
            name="uq_prescription_sequence_clinic_kind_year",
        ),
    )

    op.add_column(
        "prescriptions",
        sa.Column("serial_number", sa.String(32), nullable=True),
    )
    op.create_index(
        "idx_prescription_serial",
        "prescriptions",
        ["clinic_id", "serial_number"],
    )


def downgrade() -> None:
    op.drop_index("idx_prescription_serial", table_name="prescriptions")
    op.drop_column("prescriptions", "serial_number")
    op.drop_table("prescription_sequences")
