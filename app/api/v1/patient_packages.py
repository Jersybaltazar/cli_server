"""Endpoints REST para inscripción de pacientes en paquetes y pagos parciales."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.patient_package import PatientPackageStatus
from app.models.user import User, UserRole
from app.schemas.patient_package import (
    PackagePaymentCreate,
    PatientPackageEnroll,
    PatientPackageListResponse,
    PatientPackageResponse,
)
from app.services import patient_package_service

router = APIRouter()

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
)

_ENROLL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
)

_ALL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)


@router.get("", response_model=PatientPackageListResponse)
async def list_patient_packages(
    patient_id: UUID | None = Query(None, description="Filtrar por paciente"),
    status: PatientPackageStatus | None = Query(None, description="Filtrar por estado"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista paquetes inscritos con historial de pagos."""
    return await patient_package_service.list_patient_packages(
        db,
        clinic_id=user.clinic_id,
        patient_id=patient_id,
        status=status,
        page=page,
        size=size,
    )


@router.get("/{patient_package_id}", response_model=PatientPackageResponse)
async def get_patient_package(
    patient_package_id: UUID,
    user: User = Depends(require_role(*_ALL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un paquete inscrito con pagos."""
    return await patient_package_service.get_patient_package(
        db, clinic_id=user.clinic_id, patient_package_id=patient_package_id
    )


@router.post("", response_model=PatientPackageResponse, status_code=201)
async def enroll_patient(
    data: PatientPackageEnroll,
    user: User = Depends(require_role(*_ENROLL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Inscribe un paciente en un paquete (admin/recepción)."""
    return await patient_package_service.enroll_patient(
        db, clinic_id=user.clinic_id, user=user, data=data
    )


@router.post(
    "/{patient_package_id}/payments",
    response_model=PatientPackageResponse,
    status_code=201,
)
async def register_payment(
    patient_package_id: UUID,
    data: PackagePaymentCreate,
    user: User = Depends(require_role(*_ENROLL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Registra un pago parcial o total para un paquete inscrito."""
    return await patient_package_service.register_payment(
        db,
        clinic_id=user.clinic_id,
        user=user,
        patient_package_id=patient_package_id,
        data=data,
    )
