"""Hito 5: WhatsApp channel, reminder_sent_at, procedure_supplies

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-02-27

Hito 5: WhatsApp + Recordatorios + Procedimiento→Insumos
- Agrega enum messagechannel y columna channel a sms_messages
- Agrega reminder_sent_at a appointments
- Crea tabla procedure_supplies
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Cleanup seguro (idempotente) ─────────────────
    op.execute("DROP TABLE IF EXISTS procedure_supplies CASCADE")
    op.execute("DROP TYPE IF EXISTS messagechannel CASCADE")

    # ── 1. Crear enum messagechannel ─────────────────
    op.execute("CREATE TYPE messagechannel AS ENUM ('sms', 'whatsapp')")

    messagechannel_enum = postgresql.ENUM(
        'sms', 'whatsapp',
        name='messagechannel',
        create_type=False,
    )

    # ── 2. Agregar columna channel a sms_messages ────
    op.add_column(
        'sms_messages',
        sa.Column(
            'channel',
            messagechannel_enum,
            nullable=False,
            server_default='sms',
            comment='Canal de envío: sms o whatsapp',
        ),
    )

    # ── 3. Agregar reminder_sent_at a appointments ───
    op.add_column(
        'appointments',
        sa.Column(
            'reminder_sent_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Fecha/hora en que se envió el recordatorio',
        ),
    )

    # ── 4. Crear tabla procedure_supplies ────────────
    op.create_table(
        'procedure_supplies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id'), nullable=False),
        sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            'clinic_id', 'service_id', 'item_id',
            name='uq_procedure_supply_clinic_service_item',
        ),
    )

    op.create_index(
        'idx_proc_supply_clinic_service',
        'procedure_supplies',
        ['clinic_id', 'service_id'],
    )


def downgrade() -> None:
    op.drop_index('idx_proc_supply_clinic_service', table_name='procedure_supplies')
    op.drop_table('procedure_supplies')
    op.drop_column('appointments', 'reminder_sent_at')
    op.drop_column('sms_messages', 'channel')
    op.execute("DROP TYPE IF EXISTS messagechannel CASCADE")
