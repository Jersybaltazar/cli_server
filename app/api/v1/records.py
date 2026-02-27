"""
Endpoints de Historia Clínica Electrónica (HCE).
Solo doctores y super_admin pueden crear registros.
Receptionist NO puede ver HCE (NTS 139 Cap. VII).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.medical_record import RecordType
from app.models.user import User, UserRole
from app.schemas.medical_record import (
    MedicalRecordCreate,
    MedicalRecordListResponse,
    MedicalRecordResponse,
    SignRecordRequest,
)
from app.services import medical_record_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=MedicalRecordResponse, status_code=201)
async def create_record(
    data: MedicalRecordCreate,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA)),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un nuevo registro clínico (INSERT-only).
    Solo doctores y super_admin.
    """
    return await medical_record_service.create_record(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.get("", response_model=MedicalRecordListResponse)
async def list_patient_records(
    patient_id: UUID = Query(..., description="ID del paciente"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    record_type: RecordType | None = Query(None, description="Filtrar por tipo"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Historial clínico de un paciente (paginado).
    Receptionist NO tiene acceso.
    """
    return await medical_record_service.list_patient_records(
        db,
        user=user,
        patient_id=patient_id,
        page=page,
        size=size,
        record_type=record_type,
    )


@router.get("/{record_id}", response_model=MedicalRecordResponse)
async def get_record(
    record_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un registro clínico. Receptionist NO tiene acceso."""
    return await medical_record_service.get_record(
        db, record_id=record_id, user=user
    )


@router.post("/{record_id}/sign", response_model=MedicalRecordResponse)
async def sign_record(
    record_id: UUID,
    data: SignRecordRequest,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA)),
    db: AsyncSession = Depends(get_db),
):
    """
    Firma un registro clínico. **ACCIÓN IRREVERSIBLE**.
    Una vez firmado, el registro no puede ser modificado.
    Solo el doctor que creó el registro puede firmarlo.
    """
    if not data.confirm:
        from app.core.exceptions import ValidationException
        raise ValidationException("Debe confirmar la firma (confirm=true)")

    return await medical_record_service.sign_record(
        db, record_id=record_id, user=user, ip_address=_get_client_ip(request)
    )
