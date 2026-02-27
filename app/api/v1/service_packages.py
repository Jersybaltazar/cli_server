"""Endpoints REST para paquetes de servicios (ServicePackage)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.service_package import (
    ServicePackageCreate,
    ServicePackageListResponse,
    ServicePackageResponse,
    ServicePackageUpdate,
)
from app.services import service_package_service

router = APIRouter()

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
)

_ALL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)


@router.get("", response_model=ServicePackageListResponse)
async def list_packages(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, description="Buscar por nombre"),
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista paquetes de servicios de la clínica."""
    return await service_package_service.list_packages(
        db,
        clinic_id=user.clinic_id,
        page=page,
        size=size,
        is_active=is_active,
        search=search,
    )


@router.get("/{package_id}", response_model=ServicePackageResponse)
async def get_package(
    package_id: UUID,
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un paquete con sus ítems."""
    return await service_package_service.get_package(
        db, clinic_id=user.clinic_id, package_id=package_id
    )


@router.post("", response_model=ServicePackageResponse, status_code=201)
async def create_package(
    data: ServicePackageCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un paquete de servicios con ítems (solo admin)."""
    return await service_package_service.create_package(
        db, clinic_id=user.clinic_id, data=data
    )


@router.patch("/{package_id}", response_model=ServicePackageResponse)
async def update_package(
    package_id: UUID,
    data: ServicePackageUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un paquete (solo admin)."""
    return await service_package_service.update_package(
        db, clinic_id=user.clinic_id, package_id=package_id, data=data
    )


@router.delete("/{package_id}", status_code=204)
async def delete_package(
    package_id: UUID,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Desactiva un paquete (soft delete, solo admin)."""
    await service_package_service.delete_package(
        db, clinic_id=user.clinic_id, package_id=package_id
    )
