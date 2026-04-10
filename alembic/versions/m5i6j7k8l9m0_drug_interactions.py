"""Fase 2.4 — Interacciones medicamentosas (DDI)

Revision ID: m5i6j7k8l9m0
Revises: l4h5i6j7k8l9
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "m5i6j7k8l9m0"
down_revision = "l4h5i6j7k8l9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Tabla de interacciones ──────────────────────────
    op.create_table(
        "drug_interactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("drug_a", sa.String(255), nullable=False, comment="DCI del primer medicamento (normalizado lowercase)"),
        sa.Column("drug_b", sa.String(255), nullable=False, comment="DCI del segundo medicamento (normalizado lowercase)"),
        sa.Column("severity", sa.String(20), nullable=False, comment="contraindicated | major | moderate | minor"),
        sa.Column("description", sa.Text, nullable=False, comment="Descripción clínica breve"),
        sa.Column("recommendation", sa.Text, nullable=True, comment="Recomendación clínica"),
    )

    op.create_index("idx_ddi_drug_a", "drug_interactions", ["drug_a"])
    op.create_index("idx_ddi_drug_b", "drug_interactions", ["drug_b"])
    op.create_index("idx_ddi_pair", "drug_interactions", ["drug_a", "drug_b"], unique=True)

    # ── Campo auditoría DDI en prescriptions ────────────
    op.add_column(
        "prescriptions",
        sa.Column(
            "acknowledged_interactions",
            JSONB,
            nullable=True,
            comment="Interacciones major/contraindicated aceptadas al firmar (auditoría)",
        ),
    )


def downgrade() -> None:
    op.drop_column("prescriptions", "acknowledged_interactions")
    op.drop_index("idx_ddi_pair", table_name="drug_interactions")
    op.drop_index("idx_ddi_drug_b", table_name="drug_interactions")
    op.drop_index("idx_ddi_drug_a", table_name="drug_interactions")
    op.drop_table("drug_interactions")
