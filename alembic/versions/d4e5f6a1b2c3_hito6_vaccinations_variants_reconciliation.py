"""Hito 6: vaccinations, service_price_variants, bank_reconciliations

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-02-27

Hito 6: Dashboards, Vacunación, Variantes, Conciliación
- Crea tabla vaccine_schemes (catálogo de esquemas de vacunas)
- Crea tabla patient_vaccinations (registro de dosis)
- Crea tabla service_price_variants (variantes: gemelar, fin de semana)
- Crea tabla bank_reconciliations (conciliación Yape/transferencias)
- Crea enums modifiertype y reconciliationstatus
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, None] = 'c3d4e5f6a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Cleanup seguro (idempotente) ─────────────────
    op.execute("DROP TABLE IF EXISTS bank_reconciliations CASCADE")
    op.execute("DROP TABLE IF EXISTS service_price_variants CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_vaccinations CASCADE")
    op.execute("DROP TABLE IF EXISTS vaccine_schemes CASCADE")
    op.execute("DROP TYPE IF EXISTS modifiertype CASCADE")
    op.execute("DROP TYPE IF EXISTS reconciliationstatus CASCADE")

    # ── 1. Crear enums ───────────────────────────────
    op.execute("CREATE TYPE modifiertype AS ENUM ('fixed_surcharge', 'percentage_surcharge')")
    op.execute("CREATE TYPE reconciliationstatus AS ENUM ('pending', 'matched', 'discrepancy')")

    modifiertype_enum = postgresql.ENUM(
        'fixed_surcharge', 'percentage_surcharge',
        name='modifiertype', create_type=False,
    )
    reconciliationstatus_enum = postgresql.ENUM(
        'pending', 'matched', 'discrepancy',
        name='reconciliationstatus', create_type=False,
    )

    # ── 2. vaccine_schemes ───────────────────────────
    op.create_table(
        'vaccine_schemes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('doses_total', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('dose_intervals_months', JSONB, nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 3. patient_vaccinations ──────────────────────
    op.create_table(
        'patient_vaccinations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('patient_id', UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('vaccine_scheme_id', UUID(as_uuid=True), sa.ForeignKey('vaccine_schemes.id'), nullable=False),
        sa.Column('dose_number', sa.Integer(), nullable=False),
        sa.Column('administered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('administered_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('lot_number', sa.String(50), nullable=True),
        sa.Column('next_dose_date', sa.Date(), nullable=True),
        sa.Column('inventory_item_id', UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_vaccination_patient', 'patient_vaccinations', ['patient_id'])
    op.create_index('idx_vaccination_clinic_patient', 'patient_vaccinations', ['clinic_id', 'patient_id'])
    op.create_index('idx_vaccination_next_dose', 'patient_vaccinations', ['next_dose_date'])

    # ── 4. service_price_variants ────────────────────
    op.create_table(
        'service_price_variants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id'), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('modifier_type', modifiertype_enum, nullable=False),
        sa.Column('modifier_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('clinic_id', 'service_id', 'label', name='uq_variant_clinic_service_label'),
    )
    op.create_index('idx_variant_clinic_service', 'service_price_variants', ['clinic_id', 'service_id'])

    # ── 5. bank_reconciliations ──────────────────────
    op.create_table(
        'bank_reconciliations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('cash_movement_id', UUID(as_uuid=True), sa.ForeignKey('cash_movements.id'), nullable=False),
        sa.Column('expected_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('actual_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('status', reconciliationstatus_enum, nullable=False, server_default='pending'),
        sa.Column('bank_reference', sa.String(200), nullable=True),
        sa.Column('reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reconciled_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_recon_clinic_status', 'bank_reconciliations', ['clinic_id', 'status'])
    op.create_index('idx_recon_cash_movement', 'bank_reconciliations', ['cash_movement_id'])


def downgrade() -> None:
    op.drop_index('idx_recon_cash_movement', table_name='bank_reconciliations')
    op.drop_index('idx_recon_clinic_status', table_name='bank_reconciliations')
    op.drop_table('bank_reconciliations')

    op.drop_index('idx_variant_clinic_service', table_name='service_price_variants')
    op.drop_table('service_price_variants')

    op.drop_index('idx_vaccination_next_dose', table_name='patient_vaccinations')
    op.drop_index('idx_vaccination_clinic_patient', table_name='patient_vaccinations')
    op.drop_index('idx_vaccination_patient', table_name='patient_vaccinations')
    op.drop_table('patient_vaccinations')

    op.drop_table('vaccine_schemes')

    op.execute("DROP TYPE IF EXISTS reconciliationstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS modifiertype CASCADE")
