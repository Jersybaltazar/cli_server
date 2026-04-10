"""Fase 2.3 — Recetas controladas

Revision ID: l4h5i6j7k8l9
Revises: k3g4h5i6j7k8
Create Date: 2026-04-09

- prescriptions.kind (common/controlled) con default 'common'
- prescriptions.valid_until (vigencia máxima)
- users.is_authorized_controlled / controlled_authorization_number /
  controlled_authorization_expiry — autorización DIGEMID del médico.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l4h5i6j7k8l9"
down_revision: Union[str, None] = "k3g4h5i6j7k8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Prescriptions ────────────────────────────────
    op.add_column(
        "prescriptions",
        sa.Column(
            "kind", sa.String(20),
            nullable=False, server_default="common",
            comment="Tipo de receta: common | controlled",
        ),
    )
    op.add_column(
        "prescriptions",
        sa.Column(
            "valid_until", sa.Date(), nullable=True,
            comment="Vigencia máxima (3 días para controladas)",
        ),
    )
    op.create_index(
        "idx_prescription_kind", "prescriptions", ["clinic_id", "kind"]
    )

    # ── Users ────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "is_authorized_controlled", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "controlled_authorization_number", sa.String(60), nullable=True
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "controlled_authorization_expiry", sa.Date(), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "controlled_authorization_expiry")
    op.drop_column("users", "controlled_authorization_number")
    op.drop_column("users", "is_authorized_controlled")

    op.drop_index("idx_prescription_kind", table_name="prescriptions")
    op.drop_column("prescriptions", "valid_until")
    op.drop_column("prescriptions", "kind")
