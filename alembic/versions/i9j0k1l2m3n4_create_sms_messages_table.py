"""Create sms_messages table for SMS history tracking

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sms_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("sent_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "sms_type",
            sa.Enum("reminder", "confirmation", "invoice", "followup", "test", "custom", name="smstype"),
            nullable=False,
            server_default="custom",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "delivered", "failed", "simulated", name="smsstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("twilio_sid", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_sms_clinic_sent", "sms_messages", ["clinic_id", "sent_at"])
    op.create_index("idx_sms_patient", "sms_messages", ["patient_id"])


def downgrade() -> None:
    op.drop_index("idx_sms_patient", table_name="sms_messages")
    op.drop_index("idx_sms_clinic_sent", table_name="sms_messages")
    op.drop_table("sms_messages")
    op.execute("DROP TYPE IF EXISTS smstype")
    op.execute("DROP TYPE IF EXISTS smsstatus")
