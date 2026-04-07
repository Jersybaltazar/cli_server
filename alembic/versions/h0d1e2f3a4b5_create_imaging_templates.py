"""Create imaging_templates table

Revision ID: h0d1e2f3a4b5
Revises: g9c0d1e2f3a4
Create Date: 2026-04-06

Fase 6 — Plantillas reutilizables de informes de imagenología por clínica.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID


revision: str = "h0d1e2f3a4b5"
down_revision: Union[str, None] = "g9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "imaging_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "study_type",
            ENUM(
                "pelvic",
                "transvaginal",
                "obstetric_first",
                "obstetric_second_third",
                "obstetric_doppler",
                "obstetric_twin",
                "obstetric_twin_doppler",
                "breast",
                "morphologic",
                "genetic",
                "hysterosonography",
                "colposcopy",
                name="imagingstudytype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("findings", JSONB, nullable=False, server_default="{}"),
        sa.Column("conclusion_items", JSONB, nullable=False, server_default="[]"),
        sa.Column("recommendations", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_imaging_tpl_clinic_type",
        "imaging_templates",
        ["clinic_id", "study_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_imaging_tpl_clinic_type", table_name="imaging_templates")
    op.drop_table("imaging_templates")
