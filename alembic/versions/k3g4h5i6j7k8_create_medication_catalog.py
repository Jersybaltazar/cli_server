"""Create medication_catalog and link prescription_items

Revision ID: k3g4h5i6j7k8
Revises: j2f3a4b5c6d7
Create Date: 2026-04-08

Fase 2 — Hito 2.2: catálogo local de medicamentos para autocomplete.
- Tabla medication_catalog (DCI, presentación, controlled flag).
- pg_trgm GIN sobre dci/commercial_name para fuzzy search.
- FK opcional medication_id en prescription_items.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID


revision: str = "k3g4h5i6j7k8"
down_revision: Union[str, None] = "j2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.create_table(
        "medication_catalog",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("dci", sa.String(255), nullable=False),
        sa.Column("commercial_name", sa.String(255), nullable=True),
        sa.Column("form", sa.String(80), nullable=True),
        sa.Column("concentration", sa.String(80), nullable=True),
        sa.Column("presentation", sa.String(160), nullable=True),
        sa.Column("route", sa.String(40), nullable=True),
        sa.Column("atc_code", sa.String(10), nullable=True),
        sa.Column("therapeutic_group", sa.String(120), nullable=True),
        sa.Column(
            "is_essential", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column(
            "is_controlled", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("controlled_list", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
    )

    op.create_index("idx_medication_dci", "medication_catalog", ["dci"])
    op.create_index(
        "idx_medication_controlled", "medication_catalog", ["is_controlled"]
    )
    op.create_index(
        "idx_medication_essential", "medication_catalog", ["is_essential"]
    )
    op.create_index(
        "idx_medication_dci_trgm",
        "medication_catalog",
        ["dci"],
        postgresql_using="gin",
        postgresql_ops={"dci": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_medication_commercial_trgm",
        "medication_catalog",
        ["commercial_name"],
        postgresql_using="gin",
        postgresql_ops={"commercial_name": "gin_trgm_ops"},
    )

    # FK opcional desde prescription_items
    op.add_column(
        "prescription_items",
        sa.Column("medication_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_prescription_items_medication",
        "prescription_items",
        "medication_catalog",
        ["medication_id"],
        ["id"],
    )
    op.create_index(
        "idx_prescription_items_medication",
        "prescription_items",
        ["medication_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_prescription_items_medication", table_name="prescription_items"
    )
    op.drop_constraint(
        "fk_prescription_items_medication",
        "prescription_items",
        type_="foreignkey",
    )
    op.drop_column("prescription_items", "medication_id")

    op.drop_index(
        "idx_medication_commercial_trgm", table_name="medication_catalog"
    )
    op.drop_index("idx_medication_dci_trgm", table_name="medication_catalog")
    op.drop_index("idx_medication_essential", table_name="medication_catalog")
    op.drop_index("idx_medication_controlled", table_name="medication_catalog")
    op.drop_index("idx_medication_dci", table_name="medication_catalog")
    op.drop_table("medication_catalog")
