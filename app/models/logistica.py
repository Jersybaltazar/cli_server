"""
Modelos de Logística — Proveedores, Artículos, Inventario, Kardex.

Gestión de insumos médicos, proveedores, entradas/salidas de stock
y trazabilidad de movimientos (Kardex).
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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────


class ItemUnit(str, enum.Enum):
    """Unidad de medida del artículo."""
    UNIT = "unidad"
    BOX = "caja"
    PACK = "paquete"
    LITER = "litro"
    KG = "kilogramo"
    ML = "mililitro"
    GRAM = "gramo"
    OTHER = "otro"


class StockMovementType(str, enum.Enum):
    """Tipo de movimiento de stock."""
    ENTRY = "entry"
    EXIT = "exit"
    ADJUSTMENT = "adjustment"


class StockMovementReason(str, enum.Enum):
    """Razón del movimiento de stock."""
    # Entradas
    PURCHASE = "purchase"
    DONATION = "donation"
    RETURN_FROM_USE = "return"
    INITIAL_STOCK = "initial"
    # Salidas
    PATIENT_USE = "patient_use"
    INTERNAL_USE = "internal_use"
    EXPIRED = "expired"
    DAMAGED = "damaged"
    # Ajustes
    PHYSICAL_COUNT = "physical_count"
    CORRECTION = "correction"


# ── Supplier ──────────────────────────────────────────


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    ruc: Mapped[str] = mapped_column(
        String(11), nullable=False, comment="RUC del proveedor"
    )
    business_name: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="Razón social"
    )
    contact_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("clinic_id", "ruc", name="uq_supplier_clinic_ruc"),
        Index("idx_supplier_clinic", "clinic_id"),
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.ruc} - {self.business_name}>"


# ── InventoryCategory ─────────────────────────────────


class InventoryCategory(Base):
    __tablename__ = "inventory_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relaciones
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem", back_populates="category"
    )

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_category_clinic_name"),
        Index("idx_cat_clinic", "clinic_id"),
    )

    def __repr__(self) -> str:
        return f"<InventoryCategory {self.name}>"


# ── InventoryItem ─────────────────────────────────────


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_categories.id")
    )
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Código interno (SKU)"
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[ItemUnit] = mapped_column(
        Enum(ItemUnit, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=ItemUnit.UNIT
    )
    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0,
        comment="Stock actual"
    )
    min_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0,
        comment="Stock mínimo para alerta"
    )
    max_stock: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), comment="Stock máximo sugerido"
    )
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0,
        comment="Costo unitario promedio"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    category: Mapped["InventoryCategory | None"] = relationship(
        "InventoryCategory", back_populates="items"
    )
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement", back_populates="item"
    )

    __table_args__ = (
        UniqueConstraint("clinic_id", "code", name="uq_item_clinic_code"),
        Index("idx_item_clinic", "clinic_id"),
        Index("idx_item_stock", "clinic_id", "current_stock"),
    )

    def __repr__(self) -> str:
        return f"<InventoryItem [{self.code}] {self.name} stock={self.current_stock}>"


# ── StockMovement ─────────────────────────────────────


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False,
        comment="Artículo afectado"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Usuario que registró el movimiento"
    )
    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, values_callable=lambda e: [x.value for x in e]),
        nullable=False
    )
    reason: Mapped[StockMovementReason] = mapped_column(
        Enum(StockMovementReason, values_callable=lambda e: [x.value for x in e]),
        nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Cantidad (siempre positiva)"
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), comment="Costo unitario en esta transacción"
    )
    total_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), comment="quantity * unit_cost"
    )
    stock_before: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Stock antes del movimiento"
    )
    stock_after: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Stock después del movimiento"
    )

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"),
        comment="Proveedor (solo para compras)"
    )
    reference: Mapped[str | None] = mapped_column(
        String(200), comment="Nro factura, guía, etc."
    )
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relaciones
    item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="movements"
    )
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    creator: Mapped["User"] = relationship("User")  # noqa: F821
    supplier: Mapped["Supplier | None"] = relationship("Supplier")

    __table_args__ = (
        Index("idx_stock_mov_item", "item_id"),
        Index("idx_stock_mov_clinic_date", "clinic_id", "created_at"),
        Index("idx_stock_mov_supplier", "supplier_id"),
    )

    def __repr__(self) -> str:
        sign = "+" if self.movement_type == StockMovementType.ENTRY else "-"
        return f"<StockMovement {sign}{self.quantity} [{self.reason.value}]>"
