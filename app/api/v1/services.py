"""
Endpoints REST para el catálogo de servicios por clínica.
CRUD de servicios médicos con precios y duración.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.service import (
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
)
from app.services import service_service

router = APIRouter()

_ALL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
)

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
)


@router.get("", response_model=ServiceListResponse)
async def list_services(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Buscar por nombre"),
    is_active: bool | None = Query(None, description="Filtrar por estado activo"),
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista paginada de servicios de la clínica."""
    return await service_service.list_services(
        db, clinic_id=user.clinic_id, page=page, size=size,
        search=search, is_active=is_active,
    )


@router.get("/active", response_model=list[ServiceResponse])
async def get_active_services(
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Todos los servicios activos (sin paginación, para dropdowns)."""
    return await service_service.get_active_services(db, clinic_id=user.clinic_id)


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: UUID,
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un servicio."""
    return await service_service.get_service(db, clinic_id=user.clinic_id, service_id=service_id)


@router.post("", response_model=ServiceResponse, status_code=201)
async def create_service(
    data: ServiceCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crear un nuevo servicio (solo admins)."""
    return await service_service.create_service(db, clinic_id=user.clinic_id, data=data)


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: UUID,
    data: ServiceUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualizar un servicio (solo admins)."""
    return await service_service.update_service(
        db, clinic_id=user.clinic_id, service_id=service_id, data=data,
    )


@router.delete("/{service_id}", status_code=204)
async def delete_service(
    service_id: UUID,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Desactivar un servicio (soft delete, solo admins)."""
    await service_service.delete_service(db, clinic_id=user.clinic_id, service_id=service_id)
