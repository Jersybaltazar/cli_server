"""
Endpoints REST para el módulo de Logística.
Proveedores, artículos, inventario y movimientos de stock (Kardex).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.logistica import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventorySummary,
    LowStockItem,
    StockMovementCreate,
    StockMovementListResponse,
    StockMovementResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.services import logistica_service

router = APIRouter()

_LOGISTICA_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)


# ── Suppliers ─────────────────────────────────────────


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    data: SupplierCreate,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nuevo proveedor."""
    return await logistica_service.create_supplier(db, user.clinic_id, data)


@router.get("/suppliers", response_model=SupplierListResponse)
async def list_suppliers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Buscar por RUC o razón social"),
    is_active: bool | None = Query(None),
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista proveedores con paginación y filtros."""
    return await logistica_service.list_suppliers(
        db, user.clinic_id, page=page, size=size, search=search, is_active=is_active
    )


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: UUID,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un proveedor."""
    return await logistica_service.get_supplier(db, user.clinic_id, supplier_id)


@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un proveedor."""
    return await logistica_service.update_supplier(db, user.clinic_id, supplier_id, data)


# ── Categories ────────────────────────────────────────


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea una categoría de artículo."""
    return await logistica_service.create_category(db, user.clinic_id, data)


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las categorías de la clínica."""
    return await logistica_service.list_categories(db, user.clinic_id)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Elimina una categoría (sin artículos vinculados)."""
    await logistica_service.delete_category(db, user.clinic_id, category_id)


# ── Items ─────────────────────────────────────────────


@router.post("/items", response_model=InventoryItemResponse, status_code=201)
async def create_item(
    data: InventoryItemCreate,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nuevo artículo en el inventario."""
    return await logistica_service.create_item(db, user.clinic_id, data)


@router.get("/items", response_model=InventoryItemListResponse)
async def list_items(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Buscar por código o nombre"),
    category_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    low_stock: bool = Query(False, description="Solo artículos con stock bajo"),
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista artículos con paginación y filtros."""
    return await logistica_service.list_items(
        db,
        user.clinic_id,
        page=page,
        size=size,
        search=search,
        category_id=category_id,
        is_active=is_active,
        low_stock_only=low_stock,
    )


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_item(
    item_id: UUID,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un artículo."""
    return await logistica_service.get_item(db, user.clinic_id, item_id)


@router.put("/items/{item_id}", response_model=InventoryItemResponse)
async def update_item(
    item_id: UUID,
    data: InventoryItemUpdate,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un artículo."""
    return await logistica_service.update_item(db, user.clinic_id, item_id, data)


# ── Movements (Kardex) ───────────────────────────────


@router.post("/movements", response_model=StockMovementResponse, status_code=201)
async def create_movement(
    data: StockMovementCreate,
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Registra un movimiento de stock (entrada, salida o ajuste)."""
    return await logistica_service.create_movement(
        db, user.clinic_id, user.id, data
    )


@router.get("/movements", response_model=StockMovementListResponse)
async def list_movements(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    item_id: UUID | None = Query(None, description="Filtrar por artículo (Kardex)"),
    movement_type: str | None = Query(None, description="entry, exit, adjustment"),
    reason: str | None = Query(None),
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista movimientos de stock con filtros opcionales."""
    return await logistica_service.list_movements(
        db,
        user.clinic_id,
        item_id=item_id,
        page=page,
        size=size,
        movement_type=movement_type,
        reason=reason,
    )


# ── Summary ───────────────────────────────────────────


@router.get("/summary", response_model=InventorySummary)
async def get_inventory_summary(
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Resumen del inventario: totales, stock bajo, sin stock."""
    return await logistica_service.get_inventory_summary(db, user.clinic_id)


@router.get("/low-stock", response_model=list[LowStockItem])
async def get_low_stock_items(
    user: User = Depends(require_role(*_LOGISTICA_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Artículos con stock bajo o sin stock."""
    return await logistica_service.get_low_stock_items(db, user.clinic_id)
