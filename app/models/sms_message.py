"""
Modelo SmsMessage — Historial de mensajes SMS enviados vía Twilio.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageChannel(str, enum.Enum):
    """Canal de envío del mensaje."""
    SMS = "sms"
    WHATSAPP = "whatsapp"


class SmsStatus(str, enum.Enum):
    """Estados de un mensaje SMS."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SIMULATED = "simulated"


class SmsType(str, enum.Enum):
    """Tipos de mensaje SMS."""
    REMINDER = "reminder"
    CONFIRMATION = "confirmation"
    INVOICE = "invoice"
    FOLLOWUP = "followup"
    TEST = "test"
    CUSTOM = "custom"


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id")
    )
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Usuario que disparó el envío (null si es automático)"
    )

    phone: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Número de destino con código de país"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sms_type: Mapped[SmsType] = mapped_column(
        Enum(SmsType, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=SmsType.CUSTOM,
    )
    status: Mapped[SmsStatus] = mapped_column(
        Enum(SmsStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=SmsStatus.PENDING,
    )
    channel: Mapped[MessageChannel] = mapped_column(
        Enum(MessageChannel, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=MessageChannel.SMS,
        comment="Canal de envío: sms o whatsapp"
    )
    twilio_sid: Mapped[str | None] = mapped_column(
        String(50), comment="SID del mensaje en Twilio"
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient | None"] = relationship("Patient")  # noqa: F821

    __table_args__ = (
        Index("idx_sms_clinic_sent", "clinic_id", "sent_at"),
        Index("idx_sms_patient", "patient_id"),
    )

    def __repr__(self) -> str:
        return f"<SmsMessage to={self.phone} status={self.status.value}>"
