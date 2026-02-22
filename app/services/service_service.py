"""
Lógica de negocio para el catálogo de servicios por clínica.
"""

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.service import Service
from app.schemas.service import (
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
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
        name=data.name,
        description=data.description,
        duration_minutes=data.duration_minutes,
        price=Decimal(str(data.price)),
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
        if key == "price" and value is not None:
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
) -> ServiceListResponse:
    query = select(Service).where(Service.clinic_id == clinic_id)

    if search:
        query = query.where(Service.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(Service.is_active == is_active)

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
