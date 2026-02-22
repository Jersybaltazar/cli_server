"""
Schemas Pydantic para el módulo de Logística.
Proveedores, categorías, artículos y movimientos de stock.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Supplier Schemas ──────────────────────────────────


class SupplierCreate(BaseModel):
    ruc: str = Field(..., min_length=11, max_length=11, description="RUC del proveedor")
    business_name: str = Field(..., min_length=2, max_length=300, description="Razón social")
    contact_name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=200)
    address: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    business_name: str | None = Field(None, min_length=2, max_length=300)
    contact_name: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=200)
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    ruc: str
    business_name: str
    contact_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    items: list[SupplierResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Category Schemas ──────────────────────────────────


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str | None = None


class CategoryResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int
    page: int
    size: int
    pages: int


# ── InventoryItem Schemas ─────────────────────────────


class InventoryItemCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Código interno (SKU)")
    name: str = Field(..., min_length=2, max_length=300)
    category_id: UUID | None = None
    description: str | None = None
    unit: str = Field("unidad", description="Unidad de medida")
    min_stock: Decimal = Field(Decimal("0"), ge=0)
    max_stock: Decimal | None = Field(None, ge=0)
    unit_cost: Decimal = Field(Decimal("0"), ge=0)


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=300)
    category_id: UUID | None = None
    description: str | None = None
    unit: str | None = None
    min_stock: Decimal | None = Field(None, ge=0)
    max_stock: Decimal | None = Field(None, ge=0)
    unit_cost: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None


class InventoryItemResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    category_id: UUID | None = None
    code: str
    name: str
    description: str | None = None
    unit: str
    current_stock: Decimal
    min_stock: Decimal
    max_stock: Decimal | None = None
    unit_cost: Decimal
    is_active: bool
    category_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemResponse]
    total: int
    page: int
    size: int
    pages: int


# ── StockMovement Schemas ─────────────────────────────


class StockMovementCreate(BaseModel):
    item_id: UUID
    movement_type: str = Field(..., description="entry, exit, adjustment")
    reason: str = Field(..., description="Razón del movimiento")
    quantity: Decimal = Field(..., gt=0, description="Cantidad (siempre positiva)")
    unit_cost: Decimal | None = Field(None, ge=0)
    supplier_id: UUID | None = None
    reference: str | None = Field(None, max_length=200)
    notes: str | None = None


class StockMovementResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    item_id: UUID
    created_by: UUID
    movement_type: str
    reason: str
    quantity: Decimal
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    stock_before: Decimal
    stock_after: Decimal
    supplier_id: UUID | None = None
    reference: str | None = None
    notes: str | None = None
    item_name: str | None = None
    item_code: str | None = None
    supplier_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StockMovementListResponse(BaseModel):
    items: list[StockMovementResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Summary Schemas ───────────────────────────────────


class InventorySummary(BaseModel):
    total_items: int
    total_value: Decimal
    low_stock_count: int
    out_of_stock_count: int


class LowStockItem(BaseModel):
    item_id: UUID
    code: str
    name: str
    current_stock: Decimal
    min_stock: Decimal
    unit: str
