"""Lógica de negocio para ServicePackage — CRUD paquetes con ítems incluidos."""

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, NotFoundException
from app.models.service import Service
from app.models.service_package import PackageItem, ServicePackage
from app.schemas.service_package import (
    PackageItemResponse,
    ServicePackageCreate,
    ServicePackageListResponse,
    ServicePackageResponse,
    ServicePackageUpdate,
)


# ── Helpers ──────────────────────────────


def _item_to_response(item: PackageItem) -> PackageItemResponse:
    return PackageItemResponse(
        id=item.id,
        package_id=item.package_id,
        service_id=item.service_id,
        quantity=item.quantity,
        description_override=item.description_override,
        gestational_week_target=item.gestational_week_target,
        service_name=item.service.name if item.service else None,
    )


def _package_to_response(pkg: ServicePackage) -> ServicePackageResponse:
    return ServicePackageResponse(
        id=pkg.id,
        clinic_id=pkg.clinic_id,
        name=pkg.name,
        description=pkg.description,
        total_price=float(pkg.total_price),
        valid_from_week=pkg.valid_from_week,
        is_active=pkg.is_active,
        auto_schedule=pkg.auto_schedule,
        items=[_item_to_response(i) for i in pkg.items],
        created_at=pkg.created_at,
        updated_at=pkg.updated_at,
    )


# ── CREATE ───────────────────────────────


async def create_package(
    db: AsyncSession,
    clinic_id: UUID,
    data: ServicePackageCreate,
) -> ServicePackageResponse:
    """Crea un paquete de servicios con sus ítems."""

    # Verificar nombre único
    existing = await db.execute(
        select(ServicePackage).where(
            ServicePackage.clinic_id == clinic_id,
            ServicePackage.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Ya existe un paquete con nombre '{data.name}'")

    pkg = ServicePackage(
        clinic_id=clinic_id,
        name=data.name,
        description=data.description,
        total_price=Decimal(str(data.total_price)),
        valid_from_week=data.valid_from_week,
        is_active=data.is_active,
        auto_schedule=data.auto_schedule,
    )
    db.add(pkg)
    await db.flush()  # Obtener pkg.id para los ítems

    for item_data in data.items:
        item = PackageItem(
            package_id=pkg.id,
            service_id=item_data.service_id,
            quantity=item_data.quantity,
            description_override=item_data.description_override,
            gestational_week_target=item_data.gestational_week_target,
        )
        db.add(item)

    await db.commit()

    # Recargar con relaciones
    return await get_package(db, clinic_id=clinic_id, package_id=pkg.id)


# ── READ (single) ───────────────────────


async def get_package(
    db: AsyncSession,
    clinic_id: UUID,
    package_id: UUID,
) -> ServicePackageResponse:
    """Obtiene detalle de un paquete con sus ítems."""
    result = await db.execute(
        select(ServicePackage)
        .where(
            ServicePackage.id == package_id,
            ServicePackage.clinic_id == clinic_id,
        )
        .options(
            selectinload(ServicePackage.items).selectinload(PackageItem.service)
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise NotFoundException("Paquete")
    return _package_to_response(pkg)


# ── READ (list) ─────────────────────────


async def list_packages(
    db: AsyncSession,
    clinic_id: UUID,
    page: int = 1,
    size: int = 20,
    is_active: bool | None = None,
    search: str | None = None,
) -> ServicePackageListResponse:
    """Lista paquetes con paginación."""
    query = select(ServicePackage).where(ServicePackage.clinic_id == clinic_id)

    if is_active is not None:
        query = query.where(ServicePackage.is_active == is_active)
    if search:
        query = query.where(ServicePackage.name.ilike(f"%{search}%"))

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    # Paginar con ítems cargados
    query = (
        query
        .options(
            selectinload(ServicePackage.items).selectinload(PackageItem.service)
        )
        .order_by(ServicePackage.name)
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    packages = result.scalars().unique().all()

    return ServicePackageListResponse(
        items=[_package_to_response(p) for p in packages],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ── UPDATE ───────────────────────────────


async def update_package(
    db: AsyncSession,
    clinic_id: UUID,
    package_id: UUID,
    data: ServicePackageUpdate,
) -> ServicePackageResponse:
    """Actualiza un paquete. Si se envían items, reemplaza todos."""
    result = await db.execute(
        select(ServicePackage)
        .where(
            ServicePackage.id == package_id,
            ServicePackage.clinic_id == clinic_id,
        )
        .options(selectinload(ServicePackage.items))
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise NotFoundException("Paquete")

    update_data = data.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)

    # Verificar nombre único si cambia
    if "name" in update_data and update_data["name"] != pkg.name:
        existing = await db.execute(
            select(ServicePackage).where(
                ServicePackage.clinic_id == clinic_id,
                ServicePackage.name == update_data["name"],
                ServicePackage.id != package_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(
                f"Ya existe un paquete con nombre '{update_data['name']}'"
            )

    for key, value in update_data.items():
        if key == "total_price" and value is not None:
            value = Decimal(str(value))
        setattr(pkg, key, value)

    # Reemplazar ítems si se enviaron
    if items_data is not None:
        # Eliminar ítems existentes
        for old_item in list(pkg.items):
            await db.delete(old_item)

        # Crear nuevos
        for item_data in items_data:
            item = PackageItem(
                package_id=pkg.id,
                service_id=item_data["service_id"],
                quantity=item_data.get("quantity", 1),
                description_override=item_data.get("description_override"),
                gestational_week_target=item_data.get("gestational_week_target"),
            )
            db.add(item)

    await db.commit()
    return await get_package(db, clinic_id=clinic_id, package_id=pkg.id)


# ── DELETE (soft) ────────────────────────


async def delete_package(
    db: AsyncSession,
    clinic_id: UUID,
    package_id: UUID,
) -> None:
    """Desactiva un paquete (soft delete)."""
    result = await db.execute(
        select(ServicePackage).where(
            ServicePackage.id == package_id,
            ServicePackage.clinic_id == clinic_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise NotFoundException("Paquete")

    pkg.is_active = False
    await db.commit()
