"""create commission_rules, commission_entries, accounts_receivable, ar_payments,
accounts_payable, ap_payments

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-02-25

Hito 3: Comisiones Médicas + Cuentas por Cobrar/Pagar
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Limpiar restos de corridas fallidas
    op.execute("DROP TABLE IF EXISTS ap_payments CASCADE")
    op.execute("DROP TABLE IF EXISTS accounts_payable CASCADE")
    op.execute("DROP TABLE IF EXISTS ar_payments CASCADE")
    op.execute("DROP TABLE IF EXISTS accounts_receivable CASCADE")
    op.execute("DROP TABLE IF EXISTS commission_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS commission_rules CASCADE")
    op.execute("DROP TYPE IF EXISTS commissiontype")
    op.execute("DROP TYPE IF EXISTS commissionentrystatus")
    op.execute("DROP TYPE IF EXISTS accountstatus")

    # 1. Crear enums
    op.execute("CREATE TYPE commissiontype AS ENUM ('percentage', 'fixed')")
    op.execute("CREATE TYPE commissionentrystatus AS ENUM ('pending', 'paid')")
    op.execute("CREATE TYPE accountstatus AS ENUM ('pending', 'partial', 'paid', 'overdue')")

    # 2. commission_rules
    op.create_table(
        'commission_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('doctor_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True,
                  comment='Null = regla default para todos los doctores'),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id'), nullable=False),
        sa.Column('commission_type',
                  postgresql.ENUM('percentage', 'fixed', name='commissiontype', create_type=False),
                  nullable=False),
        sa.Column('value', sa.Numeric(12, 2), nullable=False,
                  comment='Porcentaje (0-100) o monto fijo según commission_type'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('clinic_id', 'doctor_id', 'service_id',
                            name='uq_commission_rule_clinic_doctor_service'),
    )
    op.create_index('idx_commission_rule_clinic', 'commission_rules', ['clinic_id'])

    # 3. commission_entries
    op.create_table(
        'commission_entries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('doctor_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('appointment_id', UUID(as_uuid=True), sa.ForeignKey('appointments.id'), nullable=True),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id'), nullable=False),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('service_amount', sa.Numeric(12, 2), nullable=False,
                  comment='Precio del servicio al momento de la cita'),
        sa.Column('commission_amount', sa.Numeric(12, 2), nullable=False,
                  comment='Monto de comisión calculado'),
        sa.Column('status',
                  postgresql.ENUM('pending', 'paid', name='commissionentrystatus', create_type=False),
                  nullable=False, server_default='pending'),
        sa.Column('period', sa.String(7), nullable=False, comment='Periodo YYYY-MM'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_reference', sa.String(200), nullable=True,
                  comment='Referencia de pago'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_commission_entry_clinic_period', 'commission_entries', ['clinic_id', 'period'])
    op.create_index('idx_commission_entry_doctor', 'commission_entries', ['doctor_id', 'period'])
    op.create_index('idx_commission_entry_status', 'commission_entries', ['clinic_id', 'status'])

    # 4. accounts_receivable
    op.create_table(
        'accounts_receivable',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('reference_type', sa.String(50), nullable=True,
                  comment='package, invoice, etc.'),
        sa.Column('reference_id', UUID(as_uuid=True), nullable=True),
        sa.Column('status',
                  postgresql.ENUM('pending', 'partial', 'paid', 'overdue',
                                  name='accountstatus', create_type=False),
                  nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ar_clinic', 'accounts_receivable', ['clinic_id'])
    op.create_index('idx_ar_patient', 'accounts_receivable', ['patient_id'])
    op.create_index('idx_ar_status', 'accounts_receivable', ['clinic_id', 'status'])

    # 5. ar_payments
    op.create_table(
        'ar_payments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('receivable_id', UUID(as_uuid=True),
                  sa.ForeignKey('accounts_receivable.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_method',
                  postgresql.ENUM('cash', 'card', 'transfer', 'yape_plin', 'other',
                                  name='paymentmethod', create_type=False),
                  nullable=False, server_default='cash'),
        sa.Column('cash_movement_id', UUID(as_uuid=True),
                  sa.ForeignKey('cash_movements.id'), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ar_payment_receivable', 'ar_payments', ['receivable_id'])

    # 6. accounts_payable
    op.create_table(
        'accounts_payable',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('suppliers.id'), nullable=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('reference', sa.String(200), nullable=True,
                  comment='Nro factura proveedor, orden de compra, etc.'),
        sa.Column('status',
                  postgresql.ENUM('pending', 'partial', 'paid', 'overdue',
                                  name='accountstatus', create_type=False),
                  nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ap_clinic', 'accounts_payable', ['clinic_id'])
    op.create_index('idx_ap_status', 'accounts_payable', ['clinic_id', 'status'])

    # 7. ap_payments
    op.create_table(
        'ap_payments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('payable_id', UUID(as_uuid=True),
                  sa.ForeignKey('accounts_payable.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_method',
                  postgresql.ENUM('cash', 'card', 'transfer', 'yape_plin', 'other',
                                  name='paymentmethod', create_type=False),
                  nullable=False, server_default='cash'),
        sa.Column('cash_movement_id', UUID(as_uuid=True),
                  sa.ForeignKey('cash_movements.id'), nullable=True),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ap_payment_payable', 'ap_payments', ['payable_id'])


def downgrade() -> None:
    op.drop_table('ap_payments')
    op.drop_table('accounts_payable')
    op.drop_table('ar_payments')
    op.drop_table('accounts_receivable')
    op.drop_table('commission_entries')
    op.drop_table('commission_rules')
    op.execute("DROP TYPE IF EXISTS commissiontype")
    op.execute("DROP TYPE IF EXISTS commissionentrystatus")
    op.execute("DROP TYPE IF EXISTS accountstatus")
