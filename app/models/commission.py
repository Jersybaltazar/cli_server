"""
Modelos CommissionRule + CommissionEntry — Comisiones médicas.

Reglas de comisión por servicio (porcentaje o fijo) y entradas generadas
automáticamente al completar citas.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CommissionType(str, enum.Enum):
    """Tipo de comisión."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class CommissionEntryStatus(str, enum.Enum):
    """Estado de una entrada de comisión."""
    PENDING = "pending"
    PAID = "paid"


class CommissionRule(Base):
    __tablename__ = "commission_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Null = regla default para todos los doctores"
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    commission_type: Mapped[CommissionType] = mapped_column(
        Enum(CommissionType, values_callable=lambda e: [x.value for x in e]),
        nullable=False
    )
    value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Porcentaje (0-100) o monto fijo según commission_type"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])  # noqa: F821
    service: Mapped["Service"] = relationship("Service")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("clinic_id", "doctor_id", "service_id",
                         name="uq_commission_rule_clinic_doctor_service"),
        Index("idx_commission_rule_clinic", "clinic_id"),
    )

    def __repr__(self) -> str:
        return f"<CommissionRule {self.id} type={self.commission_type}>"


class CommissionEntry(Base):
    __tablename__ = "commission_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id")
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )

    service_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Precio del servicio al momento de la cita"
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto de comisión calculado"
    )
    status: Mapped[CommissionEntryStatus] = mapped_column(
        Enum(CommissionEntryStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=CommissionEntryStatus.PENDING
    )
    period: Mapped[str] = mapped_column(
        String(7), nullable=False,
        comment="Periodo YYYY-MM para agrupación"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_reference: Mapped[str | None] = mapped_column(
        String(200), comment="Referencia de pago (nro transferencia, etc.)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])  # noqa: F821
    service: Mapped["Service"] = relationship("Service")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821

    __table_args__ = (
        Index("idx_commission_entry_clinic_period", "clinic_id", "period"),
        Index("idx_commission_entry_doctor", "doctor_id", "period"),
        Index("idx_commission_entry_status", "clinic_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<CommissionEntry {self.id} amount={self.commission_amount} status={self.status}>"
