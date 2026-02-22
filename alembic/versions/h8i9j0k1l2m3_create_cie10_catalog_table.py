"""Create cie10_codes catalog table

Tabla de referencia global para diagnósticos CIE-10 (OMS).
Se carga desde CSV con el catálogo oficial en español.

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Habilitar extensión pg_trgm para búsqueda fuzzy
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.create_table(
        "cie10_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(10), nullable=False, unique=True, comment="Código CIE-10"),
        sa.Column("description", sa.Text(), nullable=False, comment="Descripción en español"),
        sa.Column("category", sa.String(100), nullable=False, comment="Capítulo/categoría"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_index("idx_cie10_code", "cie10_codes", ["code"])
    op.create_index("idx_cie10_category", "cie10_codes", ["category"])
    op.create_index(
        "idx_cie10_description_trgm",
        "cie10_codes",
        ["description"],
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_cie10_description_trgm", table_name="cie10_codes")
    op.drop_index("idx_cie10_category", table_name="cie10_codes")
    op.drop_index("idx_cie10_code", table_name="cie10_codes")
    op.drop_table("cie10_codes")
