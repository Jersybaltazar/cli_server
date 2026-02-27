"""create service_packages, package_items, patient_packages, package_payments

Revision ID: e5f6a7b8c9d0
Revises: d468dba4cc62
Create Date: 2026-02-25

Hito 2: Paquetes CPN + Pagos en Cuotas
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd468dba4cc62'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Limpiar restos de corridas fallidas anteriores
    op.execute("DROP TABLE IF EXISTS package_payments CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_packages CASCADE")
    op.execute("DROP TABLE IF EXISTS package_items CASCADE")
    op.execute("DROP TABLE IF EXISTS service_packages CASCADE")
    op.execute("DROP TYPE IF EXISTS patientpackagestatus")

    # 1. Crear enum nuevo
    op.execute("CREATE TYPE patientpackagestatus AS ENUM ('active', 'completed', 'cancelled')")

    # 2. Tabla service_packages
    op.create_table(
        'service_packages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('total_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('valid_from_week', sa.SmallInteger, nullable=True,
                  comment='Semana gestacional mínima para inscripción'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('auto_schedule', sa.Boolean, server_default='false',
                  comment='Genera citas automáticas al inscribir paciente'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('clinic_id', 'name', name='uq_service_package_clinic_name'),
    )
    op.create_index('idx_service_package_clinic', 'service_packages', ['clinic_id'])

    # 3. Tabla package_items
    op.create_table(
        'package_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('package_id', UUID(as_uuid=True),
                  sa.ForeignKey('service_packages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True),
                  sa.ForeignKey('services.id'), nullable=False),
        sa.Column('quantity', sa.Integer, server_default='1'),
        sa.Column('description_override', sa.String(200), nullable=True,
                  comment='Descripción personalizada que reemplaza el nombre del servicio'),
        sa.Column('gestational_week_target', sa.SmallInteger, nullable=True,
                  comment='Semana gestacional objetivo para auto-agendar'),
    )
    op.create_index('idx_package_item_package', 'package_items', ['package_id'])

    # 4. Tabla patient_packages
    op.create_table(
        'patient_packages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('package_id', UUID(as_uuid=True),
                  sa.ForeignKey('service_packages.id'), nullable=False),
        sa.Column('enrolled_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False,
                  comment='Usuario que inscribió al paciente'),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False,
                  comment='Monto total del paquete al momento de inscripción'),
        sa.Column('amount_paid', sa.Numeric(12, 2), nullable=False, server_default='0.00',
                  comment='Suma de pagos realizados'),
        sa.Column('status',
                  postgresql.ENUM('active', 'completed', 'cancelled',
                                  name='patientpackagestatus', create_type=False),
                  nullable=False, server_default='active'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_patient_package_clinic', 'patient_packages', ['clinic_id'])
    op.create_index('idx_patient_package_patient', 'patient_packages', ['patient_id'])

    # 5. Tabla package_payments
    op.create_table(
        'package_payments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_package_id', UUID(as_uuid=True),
                  sa.ForeignKey('patient_packages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, comment='Monto del pago'),
        sa.Column('payment_method',
                  postgresql.ENUM('cash', 'card', 'transfer', 'yape_plin', 'other',
                                  name='paymentmethod', create_type=False),
                  nullable=False, server_default='cash'),
        sa.Column('cash_movement_id', UUID(as_uuid=True),
                  sa.ForeignKey('cash_movements.id'), nullable=True,
                  comment='Movimiento de caja asociado'),
        sa.Column('invoice_id', UUID(as_uuid=True),
                  sa.ForeignKey('invoices.id'), nullable=True,
                  comment='Factura/boleta asociada'),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False,
                  comment='Usuario que registró el pago'),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_package_payment_patient_package', 'package_payments', ['patient_package_id'])
    op.create_index('idx_package_payment_clinic', 'package_payments', ['clinic_id'])


def downgrade() -> None:
    op.drop_table('package_payments')
    op.drop_table('patient_packages')
    op.drop_table('package_items')
    op.drop_table('service_packages')
    op.execute("DROP TYPE IF EXISTS patientpackagestatus")
