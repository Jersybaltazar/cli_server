"""
Modelo ProcedureSupply — Mapeo de servicios/procedimientos a insumos de inventario.

Define qué insumos (y en qué cantidad) se consumen al realizar un servicio.
Al completar una cita, el sistema auto-descuenta stock.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProcedureSupply(Base):
    __tablename__ = "procedure_supplies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=1,
        comment="Cantidad del insumo consumida por procedimiento"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ────────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    service: Mapped["Service"] = relationship("Service")  # noqa: F821
    item: Mapped["InventoryItem"] = relationship("InventoryItem")  # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "service_id", "item_id",
            name="uq_procedure_supply_clinic_service_item"
        ),
        Index("idx_proc_supply_clinic_service", "clinic_id", "service_id"),
    )

    def __repr__(self) -> str:
        return f"<ProcedureSupply service={self.service_id} item={self.item_id} qty={self.quantity}>"
