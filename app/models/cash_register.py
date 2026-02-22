"""
Modelos CashSession + CashMovement — Control de Caja diario.

Gestión de apertura/cierre de caja, movimientos de ingreso y egreso,
y cuadre de saldos al final del día.
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


# ── Enums ─────────────────────────────────────────────


class CashSessionStatus(str, enum.Enum):
    """Estado de la sesión de caja."""
    OPEN = "open"
    CLOSED = "closed"


class MovementType(str, enum.Enum):
    """Tipo de movimiento: ingreso o egreso."""
    INCOME = "income"
    EXPENSE = "expense"


class PaymentMethod(str, enum.Enum):
    """Método de pago del movimiento."""
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    YAPE_PLIN = "yape_plin"
    OTHER = "other"


class MovementCategory(str, enum.Enum):
    """Categoría del movimiento."""
    # Ingresos
    PATIENT_PAYMENT = "patient_payment"
    OTHER_INCOME = "other_income"
    # Egresos
    SUPPLIER_PAYMENT = "supplier_payment"
    PETTY_CASH = "petty_cash"
    REFUND = "refund"
    SALARY = "salary"
    OTHER_EXPENSE = "other_expense"


# ── CashSession ───────────────────────────────────────


class CashSession(Base):
    __tablename__ = "cash_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    opened_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Usuario que abrió la caja"
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Usuario que cerró la caja"
    )

    status: Mapped[CashSessionStatus] = mapped_column(
        Enum(CashSessionStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=CashSessionStatus.OPEN
    )
    opening_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto de fondo inicial"
    )
    expected_closing_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        comment="Monto esperado al cerrar (calculado)"
    )
    actual_closing_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        comment="Monto real contado al cerrar"
    )
    difference: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        comment="Diferencia: actual - esperado (sobrante/faltante)"
    )

    notes: Mapped[str | None] = mapped_column(Text)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    opener: Mapped["User"] = relationship("User", foreign_keys=[opened_by])  # noqa: F821
    closer: Mapped["User"] = relationship("User", foreign_keys=[closed_by])  # noqa: F821
    movements: Mapped[list["CashMovement"]] = relationship(
        "CashMovement", back_populates="session", lazy="selectin"
    )

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_cash_session_clinic_status", "clinic_id", "status"),
        Index("idx_cash_session_clinic_date", "clinic_id", "opened_at"),
    )

    def __repr__(self) -> str:
        return f"<CashSession {self.id} [{self.status.value}] apertura=S/{self.opening_amount}>"


# ── CashMovement ──────────────────────────────────────


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_sessions.id"), nullable=False,
        comment="Sesión de caja a la que pertenece"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Usuario que registró el movimiento"
    )

    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, values_callable=lambda e: [x.value for x in e]),
        nullable=False, comment="income=ingreso, expense=egreso"
    )
    category: Mapped[MovementCategory] = mapped_column(
        Enum(MovementCategory, values_callable=lambda e: [x.value for x in e]),
        nullable=False, comment="Categoría del movimiento"
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=PaymentMethod.CASH, comment="Método de pago"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto (siempre positivo)"
    )
    description: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Descripción del movimiento"
    )
    reference: Mapped[str | None] = mapped_column(
        String(100),
        comment="Referencia: nro recibo, nro factura, etc."
    )

    # ── Vínculos opcionales ──────────────────────────
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"),
        comment="Factura/boleta vinculada"
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"),
        comment="Paciente vinculado"
    )

    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    session: Mapped["CashSession"] = relationship(
        "CashSession", back_populates="movements"
    )
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    creator: Mapped["User"] = relationship("User")  # noqa: F821
    invoice: Mapped["Invoice"] = relationship("Invoice")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_movement_session", "session_id"),
        Index("idx_movement_clinic_date", "clinic_id", "created_at"),
        Index("idx_movement_invoice", "invoice_id"),
    )

    def __repr__(self) -> str:
        sign = "+" if self.movement_type == MovementType.INCOME else "-"
        return f"<CashMovement {sign}S/{self.amount} [{self.category.value}]>"
