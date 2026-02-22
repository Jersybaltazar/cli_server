"""Create cash_sessions and cash_movements tables for Caja module

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-10 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── cash_sessions ─────────────────────────────────
    op.create_table(
        'cash_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('opened_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('closed_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column(
            'status',
            sa.Enum('open', 'closed', name='cashsessionstatus'),
            nullable=False,
            server_default='open',
        ),
        sa.Column('opening_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('expected_closing_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('actual_closing_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('difference', sa.Numeric(12, 2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_cash_session_clinic_status', 'cash_sessions', ['clinic_id', 'status'])
    op.create_index('idx_cash_session_clinic_date', 'cash_sessions', ['clinic_id', 'opened_at'])

    # ── cash_movements ────────────────────────────────
    op.create_table(
        'cash_movements',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('session_id', UUID(as_uuid=True), sa.ForeignKey('cash_sessions.id'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column(
            'movement_type',
            sa.Enum('income', 'expense', name='movementtype'),
            nullable=False,
        ),
        sa.Column(
            'category',
            sa.Enum(
                'patient_payment', 'other_income',
                'supplier_payment', 'petty_cash', 'refund', 'salary', 'other_expense',
                name='movementcategory',
            ),
            nullable=False,
        ),
        sa.Column(
            'payment_method',
            sa.Enum('cash', 'card', 'transfer', 'yape_plin', 'other', name='paymentmethod'),
            nullable=False,
            server_default='cash',
        ),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('reference', sa.String(100), nullable=True),
        sa.Column('invoice_id', UUID(as_uuid=True), sa.ForeignKey('invoices.id'), nullable=True),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_movement_session', 'cash_movements', ['session_id'])
    op.create_index('idx_movement_clinic_date', 'cash_movements', ['clinic_id', 'created_at'])
    op.create_index('idx_movement_invoice', 'cash_movements', ['invoice_id'])


def downgrade() -> None:
    op.drop_table('cash_movements')
    op.drop_table('cash_sessions')

    # Limpiar enums
    op.execute("DROP TYPE IF EXISTS movementcategory")
    op.execute("DROP TYPE IF EXISTS movementtype")
    op.execute("DROP TYPE IF EXISTS paymentmethod")
    op.execute("DROP TYPE IF EXISTS cashsessionstatus")
