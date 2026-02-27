"""
Modelos AccountReceivable + AccountPayable — Cuentas por cobrar y pagar.

Soportan pagos parciales y seguimiento de balance.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
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


class AccountStatus(str, enum.Enum):
    """Estado de una cuenta por cobrar/pagar."""
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"


# ── Cuentas por Cobrar ──────────────────


class AccountReceivable(Base):
    __tablename__ = "accounts_receivable"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    reference_type: Mapped[str | None] = mapped_column(
        String(50), comment="package, invoice, etc."
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=AccountStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    payments: Mapped[list["ARPayment"]] = relationship(
        "ARPayment", back_populates="receivable",
        cascade="all, delete-orphan", order_by="ARPayment.paid_at"
    )

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.amount_paid

    __table_args__ = (
        Index("idx_ar_clinic", "clinic_id"),
        Index("idx_ar_patient", "patient_id"),
        Index("idx_ar_status", "clinic_id", "status"),
    )


class ARPayment(Base):
    __tablename__ = "ar_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receivable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts_receivable.id", ondelete="CASCADE"),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=PaymentMethod.CASH
    )
    cash_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_movements.id")
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────
    receivable: Mapped["AccountReceivable"] = relationship(
        "AccountReceivable", back_populates="payments"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821

    __table_args__ = (
        Index("idx_ar_payment_receivable", "receivable_id"),
    )


# ── Cuentas por Pagar ───────────────────


class AccountPayable(Base):
    __tablename__ = "accounts_payable"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id")
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(
        String(200), comment="Nro factura proveedor, orden de compra, etc."
    )
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=AccountStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────
    supplier: Mapped["Supplier"] = relationship("Supplier")  # noqa: F821
    payments: Mapped[list["APPayment"]] = relationship(
        "APPayment", back_populates="payable",
        cascade="all, delete-orphan", order_by="APPayment.paid_at"
    )

    @property
    def balance(self) -> Decimal:
        return self.total_amount - self.amount_paid

    __table_args__ = (
        Index("idx_ap_clinic", "clinic_id"),
        Index("idx_ap_status", "clinic_id", "status"),
    )


class APPayment(Base):
    __tablename__ = "ap_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    payable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts_payable.id", ondelete="CASCADE"),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=PaymentMethod.CASH
    )
    cash_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_movements.id")
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relationships ────────────────────
    payable: Mapped["AccountPayable"] = relationship(
        "AccountPayable", back_populates="payments"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821

    __table_args__ = (
        Index("idx_ap_payment_payable", "payable_id"),
    )
