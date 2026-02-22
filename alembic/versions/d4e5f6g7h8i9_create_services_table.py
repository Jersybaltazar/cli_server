"""create services table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-10 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column(
            "price",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
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

    op.create_index("idx_service_clinic", "services", ["clinic_id"])
    op.create_unique_constraint(
        "uq_service_clinic_name", "services", ["clinic_id", "name"]
    )

    # Seed: insertar servicios default para cada clínica existente
    conn = op.get_bind()
    clinics = conn.execute(sa.text("SELECT id FROM clinics")).fetchall()

    default_services = [
        ("Consulta General", 30, 80.00, "#3b82f6"),
        ("Limpieza Dental", 45, 120.00, "#06b6d4"),
        ("Control Prenatal", 40, 100.00, "#ec4899"),
        ("Examen Visual", 30, 150.00, "#8b5cf6"),
        ("Extracción", 60, 200.00, "#ef4444"),
        ("Ortodoncia", 45, 350.00, "#f97316"),
        ("Endodoncia", 60, 400.00, "#14b8a6"),
        ("Rehabilitación", 45, 250.00, "#22c55e"),
    ]

    for clinic_row in clinics:
        clinic_id = clinic_row[0]
        for name, duration, price, color in default_services:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO services (id, clinic_id, name, duration_minutes, price, color)
                    VALUES (gen_random_uuid(), :clinic_id, :name, :duration, :price, :color)
                    """
                ),
                {
                    "clinic_id": clinic_id,
                    "name": name,
                    "duration": duration,
                    "price": price,
                    "color": color,
                },
            )


def downgrade() -> None:
    op.drop_table("services")
