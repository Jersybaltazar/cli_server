"""fix_clinic_unique_constraints

Revision ID: 4c8845aab862
Revises: 4803cbe42115
Create Date: 2026-02-15 03:26:12.295543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c8845aab862'
down_revision: Union[str, None] = '4803cbe42115'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old constraint
    op.drop_constraint('uq_clinic_ruc_per_org', 'clinics', type_='unique')
    
    # Add new constraint
    op.create_unique_constraint('uq_clinic_branch_name_per_org', 'clinics', ['organization_id', 'branch_name'])


def downgrade() -> None:
    # Drop new constraint
    op.drop_constraint('uq_clinic_branch_name_per_org', 'clinics', type_='unique')
    
    # Add back old constraint
    op.create_unique_constraint('uq_clinic_ruc_per_org', 'clinics', ['ruc', 'organization_id'])
