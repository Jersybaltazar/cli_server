"""Hito 1: ServiceCategory, cost_price, code, booked_by, fur, OBSTETRA role

Revision ID: d468dba4cc62
Revises: 492cab8ed1c2
Create Date: 2026-02-23 17:47:13.830952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd468dba4cc62'
down_revision: Union[str, None] = '492cab8ed1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear enum ServiceCategory en PostgreSQL
    servicecategory_enum = sa.Enum(
        'CONSULTATION', 'ECOGRAPHY', 'PROCEDURE', 'LAB_EXTERNAL',
        'SURGERY', 'CPN', 'VACCINATION', 'OTHER',
        name='servicecategory',
    )
    servicecategory_enum.create(op.get_bind(), checkfirst=True)

    # 2. Agregar columnas a services
    op.add_column('services', sa.Column(
        'code', sa.String(length=20), nullable=True,
        comment='Código interno del servicio (ej: ECO-GEN, CONS-GIN)',
    ))
    op.add_column('services', sa.Column(
        'category', servicecategory_enum, nullable=False,
        server_default='OTHER',
        comment='Categoría del servicio',
    ))
    op.add_column('services', sa.Column(
        'cost_price', sa.Numeric(precision=12, scale=2), nullable=False,
        server_default='0.00',
        comment='Precio de costo (pago a proveedor/doctor) en PEN',
    ))

    # Cambiar price de Numeric(10,2) a Numeric(12,2)
    op.alter_column('services', 'price',
        existing_type=sa.NUMERIC(precision=10, scale=2),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
        existing_server_default=sa.text('0.00'),
    )

    # Índice por (clinic_id, category)
    op.create_index('idx_service_clinic_category', 'services', ['clinic_id', 'category'])

    # 3. Agregar booked_by a appointments
    op.add_column('appointments', sa.Column(
        'booked_by', sa.UUID(), nullable=True,
        comment='Usuario que creó/agendó la cita',
    ))
    op.create_foreign_key(
        'fk_appointment_booked_by', 'appointments', 'users',
        ['booked_by'], ['id'],
    )

    # 4. Agregar fur a patients
    op.add_column('patients', sa.Column(
        'fur', sa.Date(), nullable=True,
        comment='Fecha de Última Regla (FUR) para cálculo de semanas gestacionales',
    ))

    # 5. Agregar valor 'obstetra' al enum userrole
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'OBSTETRA' AFTER 'DOCTOR'")


def downgrade() -> None:
    # Nota: ALTER TYPE ... DROP VALUE no existe en PostgreSQL.
    # El valor 'obstetra' quedará en el enum tras downgrade.

    op.drop_column('patients', 'fur')

    op.drop_constraint('fk_appointment_booked_by', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'booked_by')

    op.drop_index('idx_service_clinic_category', table_name='services')

    op.alter_column('services', 'price',
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.NUMERIC(precision=10, scale=2),
        existing_nullable=False,
        existing_server_default=sa.text('0.00'),
    )

    op.drop_column('services', 'cost_price')
    op.drop_column('services', 'category')
    op.drop_column('services', 'code')

    # Eliminar el tipo enum
    sa.Enum(name='servicecategory').drop(op.get_bind(), checkfirst=True)
