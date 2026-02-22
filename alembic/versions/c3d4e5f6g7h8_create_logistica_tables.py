"""Create suppliers, inventory_categories, inventory_items, stock_movements tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── suppliers ──────────────────────────────────
    op.create_table(
        'suppliers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('ruc', sa.String(11), nullable=False),
        sa.Column('business_name', sa.String(300), nullable=False),
        sa.Column('contact_name', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_supplier_clinic', 'suppliers', ['clinic_id'])
    op.create_unique_constraint('uq_supplier_clinic_ruc', 'suppliers', ['clinic_id', 'ruc'])

    # ── inventory_categories ──────────────────────
    op.create_table(
        'inventory_categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_cat_clinic', 'inventory_categories', ['clinic_id'])
    op.create_unique_constraint('uq_category_clinic_name', 'inventory_categories', ['clinic_id', 'name'])

    # ── inventory_items ───────────────────────────
    op.create_table(
        'inventory_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('inventory_categories.id'), nullable=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'unit',
            sa.Enum(
                'unidad', 'caja', 'paquete', 'litro', 'kilogramo', 'mililitro', 'gramo', 'otro',
                name='itemunit',
            ),
            nullable=False,
            server_default='unidad',
        ),
        sa.Column('current_stock', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('min_stock', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('max_stock', sa.Numeric(12, 2), nullable=True),
        sa.Column('unit_cost', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_item_clinic', 'inventory_items', ['clinic_id'])
    op.create_index('idx_item_stock', 'inventory_items', ['clinic_id', 'current_stock'])
    op.create_unique_constraint('uq_item_clinic_code', 'inventory_items', ['clinic_id', 'code'])

    # ── stock_movements ───────────────────────────
    op.create_table(
        'stock_movements',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_id', UUID(as_uuid=True), sa.ForeignKey('clinics.id'), nullable=False),
        sa.Column('item_id', UUID(as_uuid=True), sa.ForeignKey('inventory_items.id'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column(
            'movement_type',
            sa.Enum('entry', 'exit', 'adjustment', name='stockmovementtype'),
            nullable=False,
        ),
        sa.Column(
            'reason',
            sa.Enum(
                'purchase', 'donation', 'return', 'initial',
                'patient_use', 'internal_use', 'expired', 'damaged',
                'physical_count', 'correction',
                name='stockmovementreason',
            ),
            nullable=False,
        ),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('total_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('stock_before', sa.Numeric(12, 2), nullable=False),
        sa.Column('stock_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('suppliers.id'), nullable=True),
        sa.Column('reference', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_stock_mov_item', 'stock_movements', ['item_id'])
    op.create_index('idx_stock_mov_clinic_date', 'stock_movements', ['clinic_id', 'created_at'])
    op.create_index('idx_stock_mov_supplier', 'stock_movements', ['supplier_id'])


def downgrade() -> None:
    op.drop_table('stock_movements')
    op.drop_table('inventory_items')
    op.drop_table('inventory_categories')
    op.drop_table('suppliers')

    # Limpiar enums
    op.execute("DROP TYPE IF EXISTS stockmovementreason")
    op.execute("DROP TYPE IF EXISTS stockmovementtype")
    op.execute("DROP TYPE IF EXISTS itemunit")
