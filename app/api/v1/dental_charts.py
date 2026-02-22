"""
Endpoints del odontograma: CRUD de entradas dentales,
historial por diente y odontograma completo.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.dental_chart import (
    DentalChartCreate,
    DentalChartResponse,
    FullDentalChartResponse,
)
from app.services import dental_chart_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=DentalChartResponse, status_code=201)
async def create_dental_entry(
    data: DentalChartCreate,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea una nueva entrada en el odontograma.
    Solo doctores y super_admin.
    """
    return await dental_chart_service.create_entry(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.get("/patient/{patient_id}", response_model=FullDentalChartResponse)
async def get_full_dental_chart(
    patient_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Odontograma completo: estado actual de todos los dientes
    del paciente (última entrada por diente).
    """
    return await dental_chart_service.get_full_chart(
        db, clinic_id=user.clinic_id, patient_id=patient_id
    )


@router.get("/patient/{patient_id}/tooth/{tooth_number}", response_model=list[DentalChartResponse])
async def get_tooth_history(
    patient_id: UUID,
    tooth_number: int,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Historial de tratamientos de un diente específico.
    Ordenado del más reciente al más antiguo.
    """
    return await dental_chart_service.get_tooth_history(
        db,
        clinic_id=user.clinic_id,
        patient_id=patient_id,
        tooth_number=tooth_number,
    )
