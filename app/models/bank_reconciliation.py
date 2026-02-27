"""
Modelo BankReconciliation — Conciliación de pagos digitales (Yape, transferencias).

Permite comparar el monto esperado de un movimiento de caja
contra el monto real recibido en la cuenta bancaria.
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


class ReconciliationStatus(str, enum.Enum):
    """Estados de conciliación."""
    PENDING = "pending"
    MATCHED = "matched"
    DISCREPANCY = "discrepancy"


class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    cash_movement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_movements.id"), nullable=False,
        comment="Movimiento de caja vinculado"
    )
    expected_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto esperado según el sistema"
    )
    actual_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        comment="Monto real verificado en extracto bancario"
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=ReconciliationStatus.PENDING,
    )
    bank_reference: Mapped[str | None] = mapped_column(
        String(200), comment="Referencia bancaria / código Yape / nro operación"
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Fecha de conciliación"
    )
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Usuario que concilió"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ────────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    reconciler: Mapped["User | None"] = relationship("User")  # noqa: F821

    __table_args__ = (
        Index("idx_recon_clinic_status", "clinic_id", "status"),
        Index("idx_recon_cash_movement", "cash_movement_id"),
    )

    def __repr__(self) -> str:
        return f"<BankReconciliation expected={self.expected_amount} actual={self.actual_amount} [{self.status.value}]>"
