"""add_staff_schedule_override_and_user_fields

Revision ID: 044ea13d4723
Revises: j0k1l2m3n4o5
Create Date: 2026-02-21 07:11:21.187852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '044ea13d4723'
down_revision: Union[str, None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear tabla staff_schedule_overrides
    op.create_table('staff_schedule_overrides',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('clinic_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False, comment='Médico, obstetra o personal afectado'),
        sa.Column('override_type', sa.Enum('DAY_OFF', 'VACATION', 'HOLIDAY', 'SHIFT_CHANGE', 'EXTRA_SHIFT', name='overridetype'), nullable=False),
        sa.Column('date_start', sa.Date(), nullable=False, comment='Fecha inicio (si es un solo día, start == end)'),
        sa.Column('date_end', sa.Date(), nullable=False, comment='Fecha fin'),
        sa.Column('new_start_time', sa.Time(), nullable=True, comment='Hora inicio del nuevo turno (solo para shift_change/extra_shift)'),
        sa.Column('new_end_time', sa.Time(), nullable=True, comment='Hora fin del nuevo turno (solo para shift_change/extra_shift)'),
        sa.Column('substitute_user_id', sa.UUID(), nullable=True, comment='Usuario suplente (opcional)'),
        sa.Column('reason', sa.String(length=500), nullable=True, comment='Motivo de la excepción'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['substitute_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_override_clinic_dates', 'staff_schedule_overrides', ['clinic_id', 'date_start', 'date_end'], unique=False)
    op.create_index('idx_override_user_dates', 'staff_schedule_overrides', ['user_id', 'date_start'], unique=False)

    # 2. Agregar campos al modelo User
    op.add_column('users', sa.Column('specialty_type', sa.String(length=100), nullable=True, comment='Tipo de especialidad: ginecologo, obstetra, enfermera, tecnico'))
    op.add_column('users', sa.Column('position', sa.String(length=100), nullable=True, comment='Cargo: Médico Ginecólogo, Obstetriz, Recepcionista'))


def downgrade() -> None:
    # 2. Eliminar campos del modelo User
    op.drop_column('users', 'position')
    op.drop_column('users', 'specialty_type')

    # 1. Eliminar tabla staff_schedule_overrides
    op.drop_index('idx_override_user_dates', table_name='staff_schedule_overrides')
    op.drop_index('idx_override_clinic_dates', table_name='staff_schedule_overrides')
    op.drop_table('staff_schedule_overrides')
