"""
Lógica de negocio para el catálogo de servicios por clínica.
"""

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.service import Service, ServiceCategory
from app.models.service_variant import ServicePriceVariant, ModifierType
from app.schemas.service import (
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
)
from app.schemas.service_variant import (
    ServiceVariantCreate,
    ServiceVariantResponse,
    ServiceVariantUpdate,
)


def _to_response(service: Service) -> ServiceResponse:
    return ServiceResponse.model_validate(service)


# ── CRUD ─────────────────────────────────────────────


async def create_service(
    db: AsyncSession,
    clinic_id: UUID,
    data: ServiceCreate,
) -> ServiceResponse:
    # Verificar nombre único por clínica
    existing = await db.execute(
        select(Service).where(
            Service.clinic_id == clinic_id,
            Service.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Ya existe un servicio con el nombre '{data.name}'")

    service = Service(
        clinic_id=clinic_id,
        code=data.code,
        name=data.name,
        description=data.description,
        category=data.category,
        duration_minutes=data.duration_minutes,
        price=Decimal(str(data.price)),
        cost_price=Decimal(str(data.cost_price)),
        color=data.color,
        is_active=data.is_active,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return _to_response(service)


async def update_service(
    db: AsyncSession,
    clinic_id: UUID,
    service_id: UUID,
    data: ServiceUpdate,
) -> ServiceResponse:
    result = await db.execute(
        select(Service).where(
            Service.id == service_id,
            Service.clinic_id == clinic_id,
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise NotFoundException("Servicio no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    # Verificar nombre único si se está cambiando
    if "name" in update_data and update_data["name"] != service.name:
        existing = await db.execute(
            select(Service).where(
                Service.clinic_id == clinic_id,
                Service.name == update_data["name"],
                Service.id != service_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(f"Ya existe un servicio con el nombre '{update_data['name']}'")

    for key, value in update_data.items():
        if key in ("price", "cost_price") and value is not None:
            value = Decimal(str(value))
        setattr(service, key, value)

    await db.commit()
    await db.refresh(service)
    return _to_response(service)


async def delete_service(
    db: AsyncSession,
    clinic_id: UUID,
    service_id: UUID,
) -> None:
    """Soft delete: desactiva el servicio."""
    result = await db.execute(
        select(Service).where(
            Service.id == service_id,
            Service.clinic_id == clinic_id,
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise NotFoundException("Servicio no encontrado")

    service.is_active = False
    await db.commit()


async def get_service(
    db: AsyncSession,
    clinic_id: UUID,
    service_id: UUID,
) -> ServiceResponse:
    result = await db.execute(
        select(Service).where(
            Service.id == service_id,
            Service.clinic_id == clinic_id,
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise NotFoundException("Servicio no encontrado")
    return _to_response(service)


async def list_services(
    db: AsyncSession,
    clinic_id: UUID,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
    category: ServiceCategory | None = None,
) -> ServiceListResponse:
    query = select(Service).where(Service.clinic_id == clinic_id)

    if search:
        query = query.where(Service.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(Service.is_active == is_active)
    if category is not None:
        query = query.where(Service.category == category)

    # Total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    # Paginated
    query = query.order_by(Service.name).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    services = result.scalars().all()

    return ServiceListResponse(
        items=[_to_response(s) for s in services],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


async def get_active_services(
    db: AsyncSession,
    clinic_id: UUID,
) -> list[ServiceResponse]:
    """Retorna todos los servicios activos (sin paginación, para dropdowns)."""
    result = await db.execute(
        select(Service)
        .where(Service.clinic_id == clinic_id, Service.is_active == True)
        .order_by(Service.name)
    )
    return [_to_response(s) for s in result.scalars().all()]


# ── Variantes de Precio ─────────────────────────────


async def create_service_variant(
    db: AsyncSession,
    clinic_id: UUID,
    data: ServiceVariantCreate,
) -> ServiceVariantResponse:
    """Crea una variante de precio para un servicio."""
    variant = ServicePriceVariant(
        clinic_id=clinic_id,
        service_id=data.service_id,
        label=data.label,
        modifier_type=data.modifier_type,
        modifier_value=data.modifier_value,
    )
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return await _variant_to_response(db, variant)


async def list_service_variants(
    db: AsyncSession,
    clinic_id: UUID,
    service_id: UUID | None = None,
) -> list[ServiceVariantResponse]:
    """Lista variantes de precio, opcionalmente filtradas por servicio."""
    query = (
        select(ServicePriceVariant)
        .where(ServicePriceVariant.clinic_id == clinic_id)
    )
    if service_id:
        query = query.where(ServicePriceVariant.service_id == service_id)

    query = query.order_by(ServicePriceVariant.label)
    result = await db.execute(query)
    variants = result.scalars().all()

    return [await _variant_to_response(db, v) for v in variants]


async def update_service_variant(
    db: AsyncSession,
    clinic_id: UUID,
    variant_id: UUID,
    data: ServiceVariantUpdate,
) -> ServiceVariantResponse:
    """Actualiza una variante de precio."""
    result = await db.execute(
        select(ServicePriceVariant).where(
            ServicePriceVariant.id == variant_id,
            ServicePriceVariant.clinic_id == clinic_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundException("Variante de precio no encontrada")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(variant, key, value)

    await db.commit()
    await db.refresh(variant)
    return await _variant_to_response(db, variant)


async def delete_service_variant(
    db: AsyncSession,
    clinic_id: UUID,
    variant_id: UUID,
) -> None:
    """Elimina una variante de precio."""
    result = await db.execute(
        select(ServicePriceVariant).where(
            ServicePriceVariant.id == variant_id,
            ServicePriceVariant.clinic_id == clinic_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundException("Variante de precio no encontrada")
    await db.delete(variant)
    await db.commit()


async def _variant_to_response(
    db: AsyncSession, variant: ServicePriceVariant
) -> ServiceVariantResponse:
    """Enriquece la variante con nombre del servicio y precio calculado."""
    svc = await db.execute(
        select(Service).where(Service.id == variant.service_id)
    )
    service = svc.scalar_one_or_none()
    service_name = service.name if service else None
    base_price = service.price if service else Decimal("0")

    if variant.modifier_type == ModifierType.FIXED_SURCHARGE:
        calculated = base_price + variant.modifier_value
    else:
        calculated = base_price * (1 + variant.modifier_value / 100)

    return ServiceVariantResponse(
        id=variant.id,
        clinic_id=variant.clinic_id,
        service_id=variant.service_id,
        label=variant.label,
        modifier_type=variant.modifier_type,
        modifier_value=variant.modifier_value,
        is_active=variant.is_active,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
        service_name=service_name,
        calculated_price=calculated.quantize(Decimal("0.01")),
    )
