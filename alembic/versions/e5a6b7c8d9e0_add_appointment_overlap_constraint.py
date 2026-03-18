"""Add exclusion constraint to prevent appointment overlap at DB level.

Revision ID: e5a6b7c8d9e0
Revises: d4e5f6a1b2c3
Create Date: 2026-03-18

Agrega un EXCLUDE constraint con btree_gist que impide solapamiento
de citas del mismo doctor a nivel de base de datos (race-condition safe).
"""

from alembic import op


revision = "e5a6b7c8d9e0"
down_revision = "d4e5f6a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # btree_gist es necesario para combinar = (equality) con && (overlap) en GiST
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute("""
        ALTER TABLE appointments
        ADD CONSTRAINT excl_doctor_appointment_overlap
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(start_time, end_time) WITH &&
        )
        WHERE (status NOT IN ('cancelled', 'no_show'))
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE appointments
        DROP CONSTRAINT IF EXISTS excl_doctor_appointment_overlap
    """)
