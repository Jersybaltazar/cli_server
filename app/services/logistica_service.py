"""
Lógica de negocio para el módulo de Logística.
Gestión de proveedores, artículos, inventario y movimientos de stock (Kardex).
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.logistica import (
    InventoryCategory,
    InventoryItem,
    ItemUnit,
    StockMovement,
    StockMovementReason,
    StockMovementType,
    Supplier,
)
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


# ── Helpers ───────────────────────────────────────────


def _supplier_to_response(supplier: Supplier) -> SupplierResponse:
    return SupplierResponse.model_validate(supplier)


def _category_to_response(cat: InventoryCategory) -> CategoryResponse:
    return CategoryResponse.model_validate(cat)


def _item_to_response(item: InventoryItem) -> InventoryItemResponse:
    return InventoryItemResponse(
        id=item.id,
        clinic_id=item.clinic_id,
        category_id=item.category_id,
        code=item.code,
        name=item.name,
        description=item.description,
        unit=item.unit.value if isinstance(item.unit, ItemUnit) else str(item.unit),
        current_stock=item.current_stock,
        min_stock=item.min_stock,
        max_stock=item.max_stock,
        unit_cost=item.unit_cost,
        is_active=item.is_active,
        category_name=item.category.name if item.category else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _movement_to_response(mov: StockMovement) -> StockMovementResponse:
    return StockMovementResponse(
        id=mov.id,
        clinic_id=mov.clinic_id,
        item_id=mov.item_id,
        created_by=mov.created_by,
        movement_type=mov.movement_type.value if isinstance(mov.movement_type, StockMovementType) else str(mov.movement_type),
        reason=mov.reason.value if isinstance(mov.reason, StockMovementReason) else str(mov.reason),
        quantity=mov.quantity,
        unit_cost=mov.unit_cost,
        total_cost=mov.total_cost,
        stock_before=mov.stock_before,
        stock_after=mov.stock_after,
        supplier_id=mov.supplier_id,
        reference=mov.reference,
        notes=mov.notes,
        item_name=mov.item.name if mov.item else None,
        item_code=mov.item.code if mov.item else None,
        supplier_name=mov.supplier.business_name if mov.supplier else None,
        created_at=mov.created_at,
    )


# ── Suppliers ─────────────────────────────────────────


async def create_supplier(
    db: AsyncSession, clinic_id: UUID, data: SupplierCreate
) -> SupplierResponse:
    # Validar RUC único por clínica
    existing = await db.execute(
        select(Supplier).where(
            Supplier.clinic_id == clinic_id,
            Supplier.ruc == data.ruc,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Ya existe un proveedor con RUC {data.ruc}")

    supplier = Supplier(
        clinic_id=clinic_id,
        ruc=data.ruc,
        business_name=data.business_name,
        contact_name=data.contact_name,
        phone=data.phone,
        email=data.email,
        address=data.address,
        notes=data.notes,
    )
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    return _supplier_to_response(supplier)


async def update_supplier(
    db: AsyncSession, clinic_id: UUID, supplier_id: UUID, data: SupplierUpdate
) -> SupplierResponse:
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.clinic_id == clinic_id,
        )
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundException("Proveedor no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(supplier, key, value)

    await db.flush()
    await db.refresh(supplier)
    return _supplier_to_response(supplier)


async def list_suppliers(
    db: AsyncSession,
    clinic_id: UUID,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> SupplierListResponse:
    query = select(Supplier).where(Supplier.clinic_id == clinic_id)
    count_query = select(func.count()).select_from(Supplier).where(
        Supplier.clinic_id == clinic_id
    )

    if is_active is not None:
        query = query.where(Supplier.is_active == is_active)
        count_query = count_query.where(Supplier.is_active == is_active)

    if search:
        search_filter = or_(
            Supplier.ruc.ilike(f"%{search}%"),
            Supplier.business_name.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Supplier.business_name.asc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    suppliers = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 1

    return SupplierListResponse(
        items=[_supplier_to_response(s) for s in suppliers],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


async def get_supplier(
    db: AsyncSession, clinic_id: UUID, supplier_id: UUID
) -> SupplierResponse:
    result = await db.execute(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.clinic_id == clinic_id,
        )
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundException("Proveedor no encontrado")
    return _supplier_to_response(supplier)


# ── Categories ────────────────────────────────────────


async def create_category(
    db: AsyncSession, clinic_id: UUID, data: CategoryCreate
) -> CategoryResponse:
    existing = await db.execute(
        select(InventoryCategory).where(
            InventoryCategory.clinic_id == clinic_id,
            InventoryCategory.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Ya existe la categoría '{data.name}'")

    cat = InventoryCategory(
        clinic_id=clinic_id,
        name=data.name,
        description=data.description,
    )
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return _category_to_response(cat)


async def list_categories(
    db: AsyncSession, clinic_id: UUID
) -> CategoryListResponse:
    query = select(InventoryCategory).where(
        InventoryCategory.clinic_id == clinic_id
    ).order_by(InventoryCategory.name.asc())

    count_result = await db.execute(
        select(func.count()).select_from(InventoryCategory).where(
            InventoryCategory.clinic_id == clinic_id
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(query)
    categories = result.scalars().all()

    return CategoryListResponse(
        items=[_category_to_response(c) for c in categories],
        total=total,
        page=1,
        size=total or 1,
        pages=1,
    )


async def delete_category(
    db: AsyncSession, clinic_id: UUID, category_id: UUID
) -> None:
    result = await db.execute(
        select(InventoryCategory).where(
            InventoryCategory.id == category_id,
            InventoryCategory.clinic_id == clinic_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise NotFoundException("Categoría no encontrada")

    # Verificar que no tenga items vinculados
    items_count = await db.execute(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.category_id == category_id
        )
    )
    if (items_count.scalar() or 0) > 0:
        raise ConflictException("No se puede eliminar: hay artículos vinculados a esta categoría")

    await db.delete(cat)
    await db.flush()


# ── Items ─────────────────────────────────────────────


async def create_item(
    db: AsyncSession, clinic_id: UUID, data: InventoryItemCreate
) -> InventoryItemResponse:
    # Validar código único por clínica
    existing = await db.execute(
        select(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.code == data.code,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Ya existe un artículo con código '{data.code}'")

    item = InventoryItem(
        clinic_id=clinic_id,
        code=data.code,
        name=data.name,
        category_id=data.category_id,
        description=data.description,
        unit=data.unit,
        min_stock=data.min_stock,
        max_stock=data.max_stock,
        unit_cost=data.unit_cost,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    # Cargar relación de categoría
    if item.category_id:
        cat_result = await db.execute(
            select(InventoryCategory).where(InventoryCategory.id == item.category_id)
        )
        item.category = cat_result.scalar_one_or_none()

    return _item_to_response(item)


async def update_item(
    db: AsyncSession, clinic_id: UUID, item_id: UUID, data: InventoryItemUpdate
) -> InventoryItemResponse:
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.clinic_id == clinic_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundException("Artículo no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    await db.flush()
    await db.refresh(item)

    if item.category_id:
        cat_result = await db.execute(
            select(InventoryCategory).where(InventoryCategory.id == item.category_id)
        )
        item.category = cat_result.scalar_one_or_none()

    return _item_to_response(item)


async def list_items(
    db: AsyncSession,
    clinic_id: UUID,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    category_id: UUID | None = None,
    is_active: bool | None = None,
    low_stock_only: bool = False,
) -> InventoryItemListResponse:
    query = select(InventoryItem).where(InventoryItem.clinic_id == clinic_id)
    count_query = select(func.count()).select_from(InventoryItem).where(
        InventoryItem.clinic_id == clinic_id
    )

    if is_active is not None:
        query = query.where(InventoryItem.is_active == is_active)
        count_query = count_query.where(InventoryItem.is_active == is_active)

    if category_id:
        query = query.where(InventoryItem.category_id == category_id)
        count_query = count_query.where(InventoryItem.category_id == category_id)

    if search:
        search_filter = or_(
            InventoryItem.code.ilike(f"%{search}%"),
            InventoryItem.name.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if low_stock_only:
        query = query.where(InventoryItem.current_stock <= InventoryItem.min_stock)
        count_query = count_query.where(InventoryItem.current_stock <= InventoryItem.min_stock)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(InventoryItem.name.asc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    items = result.scalars().all()

    # Cargar categorías
    for item in items:
        if item.category_id:
            cat_result = await db.execute(
                select(InventoryCategory).where(InventoryCategory.id == item.category_id)
            )
            item.category = cat_result.scalar_one_or_none()

    pages = (total + size - 1) // size if total > 0 else 1

    return InventoryItemListResponse(
        items=[_item_to_response(i) for i in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


async def get_item(
    db: AsyncSession, clinic_id: UUID, item_id: UUID
) -> InventoryItemResponse:
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.clinic_id == clinic_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundException("Artículo no encontrado")

    if item.category_id:
        cat_result = await db.execute(
            select(InventoryCategory).where(InventoryCategory.id == item.category_id)
        )
        item.category = cat_result.scalar_one_or_none()

    return _item_to_response(item)


# ── Stock Movements ───────────────────────────────────


ENTRY_REASONS = {
    StockMovementReason.PURCHASE,
    StockMovementReason.DONATION,
    StockMovementReason.RETURN_FROM_USE,
    StockMovementReason.INITIAL_STOCK,
}

EXIT_REASONS = {
    StockMovementReason.PATIENT_USE,
    StockMovementReason.INTERNAL_USE,
    StockMovementReason.EXPIRED,
    StockMovementReason.DAMAGED,
}

ADJUSTMENT_REASONS = {
    StockMovementReason.PHYSICAL_COUNT,
    StockMovementReason.CORRECTION,
}


async def create_movement(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    data: StockMovementCreate,
) -> StockMovementResponse:
    # Obtener artículo
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.id == data.item_id,
            InventoryItem.clinic_id == clinic_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundException("Artículo no encontrado")

    # Convertir enums
    try:
        movement_type = StockMovementType(data.movement_type)
    except ValueError:
        raise ValidationException(f"Tipo de movimiento inválido: {data.movement_type}")

    try:
        reason = StockMovementReason(data.reason)
    except ValueError:
        raise ValidationException(f"Razón de movimiento inválida: {data.reason}")

    # Validar razón vs tipo
    if movement_type == StockMovementType.ENTRY and reason not in ENTRY_REASONS:
        raise ValidationException("Razón inválida para una entrada")
    if movement_type == StockMovementType.EXIT and reason not in EXIT_REASONS:
        raise ValidationException("Razón inválida para una salida")
    if movement_type == StockMovementType.ADJUSTMENT and reason not in ADJUSTMENT_REASONS:
        raise ValidationException("Razón inválida para un ajuste")

    stock_before = item.current_stock
    quantity = data.quantity

    # Calcular nuevo stock
    if movement_type == StockMovementType.ENTRY:
        stock_after = stock_before + quantity
    elif movement_type == StockMovementType.EXIT:
        if stock_before < quantity:
            raise ValidationException(
                f"Stock insuficiente. Disponible: {stock_before}, solicitado: {quantity}"
            )
        stock_after = stock_before - quantity
    else:  # ADJUSTMENT
        # Para ajustes, quantity es el nuevo stock absoluto
        stock_after = quantity

    # Calcular costo total
    total_cost = None
    if data.unit_cost is not None:
        total_cost = data.quantity * data.unit_cost

    # Actualizar costo promedio ponderado (solo en entradas con costo)
    if movement_type == StockMovementType.ENTRY and data.unit_cost is not None:
        if stock_before > 0:
            new_cost = (
                (stock_before * item.unit_cost + quantity * data.unit_cost)
                / (stock_before + quantity)
            )
            item.unit_cost = new_cost
        else:
            item.unit_cost = data.unit_cost

    # Actualizar stock del artículo
    item.current_stock = stock_after

    # Crear movimiento
    movement = StockMovement(
        clinic_id=clinic_id,
        item_id=item.id,
        created_by=user_id,
        movement_type=movement_type,
        reason=reason,
        quantity=quantity if movement_type != StockMovementType.ADJUSTMENT else abs(stock_after - stock_before),
        unit_cost=data.unit_cost,
        total_cost=total_cost,
        stock_before=stock_before,
        stock_after=stock_after,
        supplier_id=data.supplier_id,
        reference=data.reference,
        notes=data.notes,
    )
    db.add(movement)
    await db.flush()
    await db.refresh(movement)
    await db.refresh(item)

    # Cargar relaciones
    movement.item = item
    if data.supplier_id:
        sup_result = await db.execute(
            select(Supplier).where(Supplier.id == data.supplier_id)
        )
        movement.supplier = sup_result.scalar_one_or_none()

    return _movement_to_response(movement)


async def list_movements(
    db: AsyncSession,
    clinic_id: UUID,
    item_id: UUID | None = None,
    page: int = 1,
    size: int = 50,
    movement_type: str | None = None,
    reason: str | None = None,
) -> StockMovementListResponse:
    query = select(StockMovement).where(
        StockMovement.clinic_id == clinic_id
    ).options(
        selectinload(StockMovement.item),
        selectinload(StockMovement.supplier),
    )
    count_query = select(func.count()).select_from(StockMovement).where(
        StockMovement.clinic_id == clinic_id
    )

    if item_id:
        query = query.where(StockMovement.item_id == item_id)
        count_query = count_query.where(StockMovement.item_id == item_id)

    if movement_type:
        try:
            mt = StockMovementType(movement_type)
            query = query.where(StockMovement.movement_type == mt)
            count_query = count_query.where(StockMovement.movement_type == mt)
        except ValueError:
            pass

    if reason:
        try:
            r = StockMovementReason(reason)
            query = query.where(StockMovement.reason == r)
            count_query = count_query.where(StockMovement.reason == r)
        except ValueError:
            pass

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(StockMovement.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    movements = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 1

    return StockMovementListResponse(
        items=[_movement_to_response(m) for m in movements],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ── Summary ───────────────────────────────────────────


async def get_inventory_summary(
    db: AsyncSession, clinic_id: UUID
) -> InventorySummary:
    # Total artículos activos
    total_result = await db.execute(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.is_active.is_(True),
        )
    )
    total_items = total_result.scalar() or 0

    # Valor total del inventario
    value_result = await db.execute(
        select(func.coalesce(func.sum(InventoryItem.current_stock * InventoryItem.unit_cost), 0)).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.is_active.is_(True),
        )
    )
    total_value = Decimal(str(value_result.scalar()))

    # Stock bajo
    low_result = await db.execute(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.is_active.is_(True),
            InventoryItem.current_stock <= InventoryItem.min_stock,
            InventoryItem.current_stock > 0,
        )
    )
    low_stock_count = low_result.scalar() or 0

    # Sin stock
    out_result = await db.execute(
        select(func.count()).select_from(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.is_active.is_(True),
            InventoryItem.current_stock <= 0,
        )
    )
    out_of_stock_count = out_result.scalar() or 0

    return InventorySummary(
        total_items=total_items,
        total_value=total_value,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
    )


async def get_low_stock_items(
    db: AsyncSession, clinic_id: UUID
) -> list[LowStockItem]:
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.is_active.is_(True),
            InventoryItem.current_stock <= InventoryItem.min_stock,
        ).order_by(InventoryItem.current_stock.asc()).limit(50)
    )
    items = result.scalars().all()

    return [
        LowStockItem(
            item_id=item.id,
            code=item.code,
            name=item.name,
            current_stock=item.current_stock,
            min_stock=item.min_stock,
            unit=item.unit.value if isinstance(item.unit, ItemUnit) else str(item.unit),
        )
        for item in items
    ]
