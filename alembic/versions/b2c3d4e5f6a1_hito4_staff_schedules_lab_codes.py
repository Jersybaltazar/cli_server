"""Hito 4: staff_schedules, lab_sequences, lab_order columns (lab_code,
cassette_count, delivery_channel, delivered_by)

Revision ID: b2c3d4e5f6a1
Revises: f7a8b9c0d1e2
Create Date: 2026-02-25

Hito 4: Turnos Generalizados + Calendario Mensual + Códigos Lab
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Limpiar restos de corridas fallidas
    op.execute("DROP TABLE IF EXISTS staff_schedules CASCADE")
    op.execute("DROP TABLE IF EXISTS lab_sequences CASCADE")
    op.execute("DROP TYPE IF EXISTS deliverychannel")

    # 1. Crear enum deliverychannel
    op.execute(
        "CREATE TYPE deliverychannel AS ENUM "
        "('whatsapp', 'printed', 'in_person', 'email', 'not_delivered')"
    )

    # 2. staff_schedules
    op.create_table(
        'staff_schedules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('day_of_week', sa.SmallInteger, nullable=False,
                  comment='0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo'),
        sa.Column('start_time', sa.Time, nullable=False),
        sa.Column('end_time', sa.Time, nullable=False),
        sa.Column('shift_label', sa.String(50), nullable=True, comment='mañana, tarde, noche'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
    )
    op.create_index('idx_staff_schedule_user_day', 'staff_schedules', ['user_id', 'day_of_week'])
    op.create_index('idx_staff_schedule_clinic', 'staff_schedules', ['clinic_id', 'is_active'])

    # 3. lab_sequences
    op.create_table(
        'lab_sequences',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('sequence_type', sa.String(20), nullable=False, comment='pathology o cytology'),
        sa.Column('year', sa.SmallInteger, nullable=False),
        sa.Column('last_number', sa.Integer, nullable=False, server_default='0'),
        sa.UniqueConstraint('clinic_id', 'sequence_type', 'year',
                            name='uq_lab_sequence_clinic_type_year'),
    )

    # 4. Agregar columnas a lab_orders
    op.add_column('lab_orders', sa.Column(
        'lab_code', sa.String(20), nullable=True,
        comment='Código secuencial: M26-XX (patología), C26-XX (citología)'
    ))
    op.add_column('lab_orders', sa.Column(
        'cassette_count', sa.SmallInteger, nullable=True,
        comment='Cantidad de cassettes para muestras de patología'
    ))
    op.add_column('lab_orders', sa.Column(
        'delivery_channel',
        postgresql.ENUM('whatsapp', 'printed', 'in_person', 'email', 'not_delivered',
                        name='deliverychannel', create_type=False),
        nullable=True,
        comment='Canal por el cual se entregó el resultado'
    ))
    op.add_column('lab_orders', sa.Column(
        'delivered_by', UUID(as_uuid=True),
        sa.ForeignKey('users.id'), nullable=True,
        comment='Usuario que entregó el resultado'
    ))


def downgrade() -> None:
    # Quitar columnas de lab_orders
    op.drop_column('lab_orders', 'delivered_by')
    op.drop_column('lab_orders', 'delivery_channel')
    op.drop_column('lab_orders', 'cassette_count')
    op.drop_column('lab_orders', 'lab_code')

    # Quitar tablas
    op.drop_table('lab_sequences')
    op.drop_table('staff_schedules')

    # Quitar enum
    op.execute("DROP TYPE IF EXISTS deliverychannel")
