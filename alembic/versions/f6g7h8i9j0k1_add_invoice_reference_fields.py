"""Add referenced_invoice_id and motivo_nota to invoices

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-02-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "referenced_invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invoices.id"),
            nullable=True,
            comment="Comprobante original referenciado (para NC/ND)",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "motivo_nota",
            sa.String(500),
            nullable=True,
            comment="Motivo de la nota de crédito/débito",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "motivo_nota")
    op.drop_column("invoices", "referenced_invoice_id")
