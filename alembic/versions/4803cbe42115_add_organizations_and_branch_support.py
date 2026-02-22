"""add_organizations_and_branch_support

Revision ID: 4803cbe42115
Revises: f6g7h8i9j0k1
Create Date: 2026-02-14 08:27:59.315723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4803cbe42115'
down_revision: Union[str, None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add ORG_ADMIN value to existing userrole enum
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'ORG_ADMIN' AFTER 'SUPER_ADMIN'")

    # 2. Create plantype enum
    plantype_enum = postgresql.ENUM('BASIC', 'PROFESSIONAL', 'ENTERPRISE', name='plantype', create_type=False)
    plantype_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create organizations table
    op.create_table('organizations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False, comment='Nombre del grupo empresarial'),
        sa.Column('ruc', sa.String(length=11), nullable=False, comment='RUC principal de la organización'),
        sa.Column('plan_type', postgresql.ENUM('BASIC', 'PROFESSIONAL', 'ENTERPRISE', name='plantype', create_type=False), nullable=False, comment='Plan de suscripción SaaS'),
        sa.Column('max_clinics', sa.Integer(), nullable=False, comment='Máximo de sedes permitidas según el plan'),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=20), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Configuraciones globales de la organización'),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_ruc'), 'organizations', ['ruc'], unique=True)

    # 4. Create user_clinic_access table (reuse existing userrole enum)
    op.create_table('user_clinic_access',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('clinic_id', sa.UUID(), nullable=False),
        sa.Column('role_in_clinic', postgresql.ENUM('SUPER_ADMIN', 'ORG_ADMIN', 'CLINIC_ADMIN', 'DOCTOR', 'RECEPTIONIST', name='userrole', create_type=False), nullable=False, comment='Rol del usuario en esta sede específica'),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'clinic_id', name='uq_user_clinic_access')
    )
    op.create_index(op.f('ix_user_clinic_access_clinic_id'), 'user_clinic_access', ['clinic_id'], unique=False)
    op.create_index(op.f('ix_user_clinic_access_user_id'), 'user_clinic_access', ['user_id'], unique=False)

    # 5. Add organization_id and branch_name to clinics
    op.add_column('clinics', sa.Column('organization_id', sa.UUID(), nullable=True, comment='Organización a la que pertenece (null = clínica independiente)'))
    op.add_column('clinics', sa.Column('branch_name', sa.String(length=100), nullable=True, comment='Nombre de la sede/sucursal (ej: Sede Lima Norte)'))
    op.create_index(op.f('ix_clinics_organization_id'), 'clinics', ['organization_id'], unique=False)
    op.create_foreign_key('fk_clinics_organization_id', 'clinics', 'organizations', ['organization_id'], ['id'])

    # 6. Update clinics RUC index (unique -> non-unique) and add composite unique
    op.drop_index('ix_clinics_ruc', table_name='clinics')
    op.create_index(op.f('ix_clinics_ruc'), 'clinics', ['ruc'], unique=False)
    op.create_unique_constraint('uq_clinic_ruc_per_org', 'clinics', ['ruc', 'organization_id'])


def downgrade() -> None:
    # Revert clinics changes
    op.drop_constraint('uq_clinic_ruc_per_org', 'clinics', type_='unique')
    op.drop_index(op.f('ix_clinics_ruc'), table_name='clinics')
    op.create_index('ix_clinics_ruc', 'clinics', ['ruc'], unique=True)
    op.drop_constraint('fk_clinics_organization_id', 'clinics', type_='foreignkey')
    op.drop_index(op.f('ix_clinics_organization_id'), table_name='clinics')
    op.drop_column('clinics', 'branch_name')
    op.drop_column('clinics', 'organization_id')

    # Drop user_clinic_access
    op.drop_index(op.f('ix_user_clinic_access_user_id'), table_name='user_clinic_access')
    op.drop_index(op.f('ix_user_clinic_access_clinic_id'), table_name='user_clinic_access')
    op.drop_table('user_clinic_access')

    # Drop organizations
    op.drop_index(op.f('ix_organizations_ruc'), table_name='organizations')
    op.drop_table('organizations')

    # Drop plantype enum
    postgresql.ENUM(name='plantype').drop(op.get_bind(), checkfirst=True)

    # Note: Cannot remove ORG_ADMIN from userrole enum in PostgreSQL
    # (ALTER TYPE ... DROP VALUE is not supported)
