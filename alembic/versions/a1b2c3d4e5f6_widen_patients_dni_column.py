"""Widen patients.dni column from varchar(20) to varchar(255) for Fernet encryption

Revision ID: a1b2c3d4e5f6
Revises: 0d7ba47a6567
Create Date: 2026-02-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0d7ba47a6567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'patients',
        'dni',
        existing_type=sa.String(length=20),
        type_=sa.String(length=255),
        existing_nullable=False,
        existing_comment='DNI cifrado con Fernet — índice sobre hash',
    )


def downgrade() -> None:
    op.alter_column(
        'patients',
        'dni',
        existing_type=sa.String(length=255),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_comment='DNI cifrado con Fernet — índice sobre hash',
    )
