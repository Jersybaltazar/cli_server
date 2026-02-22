"""add slug to clinics

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-02-20
"""

import re
import unicodedata
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def _slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "clinica"


def upgrade() -> None:
    # 1. Add slug column (nullable initially)
    op.add_column("clinics", sa.Column("slug", sa.String(250), nullable=True))

    # 2. Backfill existing clinics with slugs
    conn = op.get_bind()
    clinics = conn.execute(sa.text("SELECT id, name FROM clinics")).fetchall()
    used_slugs: dict[str, int] = {}
    for clinic_id, name in clinics:
        base_slug = _slugify(name)
        slug = base_slug
        if slug in used_slugs:
            used_slugs[slug] += 1
            slug = f"{base_slug}-{used_slugs[slug]}"
        else:
            used_slugs[slug] = 1
        conn.execute(
            sa.text("UPDATE clinics SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": clinic_id},
        )

    # 3. Add unique constraint and index
    op.create_index("ix_clinics_slug", "clinics", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_clinics_slug", table_name="clinics")
    op.drop_column("clinics", "slug")
