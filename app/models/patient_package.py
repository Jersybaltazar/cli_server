"""
Modelos PatientPackage + PackagePayment — Inscripción de paciente en paquete
y registro de pagos parciales.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.cash_register import PaymentMethod


class PatientPackageStatus(str, enum.Enum):
    """Estado de la inscripción del paciente en un paquete."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PatientPackage(Base):
    __tablename__ = "patient_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_packages.id"), nullable=False
    )
    enrolled_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Usuario que inscribió al paciente"
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto total del paquete al momento de inscripción"
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"),
        comment="Suma de pagos realizados"
    )
    status: Mapped[PatientPackageStatus] = mapped_column(
        Enum(PatientPackageStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=PatientPackageStatus.ACTIVE
    )
    notes: Mapped[str | None] = mapped_column(Text)

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    package: Mapped["ServicePackage"] = relationship("ServicePackage")  # noqa: F821
    enrolling_user: Mapped["User"] = relationship("User", foreign_keys=[enrolled_by])  # noqa: F821
    payments: Mapped[list["PackagePayment"]] = relationship(
        "PackagePayment", back_populates="patient_package",
        cascade="all, delete-orphan", order_by="PackagePayment.paid_at"
    )

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.amount_paid

    __table_args__ = (
        Index("idx_patient_package_clinic", "clinic_id"),
        Index("idx_patient_package_patient", "patient_id"),
    )

    def __repr__(self) -> str:
        return f"<PatientPackage {self.id} patient={self.patient_id} status={self.status}>"


class PackagePayment(Base):
    __tablename__ = "package_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patient_packages.id", ondelete="CASCADE"),
        nullable=False
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto del pago"
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=PaymentMethod.CASH
    )
    cash_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_movements.id"),
        comment="Movimiento de caja asociado (si aplica)"
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"),
        comment="Factura/boleta asociada (si aplica)"
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Usuario que registró el pago"
    )

    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────
    patient_package: Mapped["PatientPackage"] = relationship(
        "PatientPackage", back_populates="payments"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821

    __table_args__ = (
        Index("idx_package_payment_patient_package", "patient_package_id"),
        Index("idx_package_payment_clinic", "clinic_id"),
    )

    def __repr__(self) -> str:
        return f"<PackagePayment {self.id} amount={self.amount}>"
