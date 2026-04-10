"""Fase 2.5 — QR de verificación en recetas

Revision ID: n6j7k8l9m0n1
Revises: m5i6j7k8l9m0
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa

revision = "n6j7k8l9m0n1"
down_revision = "m5i6j7k8l9m0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column(
            "verification_token",
            sa.String(16),
            nullable=True,
            comment="HMAC-SHA256 truncado para URL pública de verificación QR",
        ),
    )


def downgrade() -> None:
    op.drop_column("prescriptions", "verification_token")
