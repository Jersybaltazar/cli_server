"""
Endpoints de control prenatal (CLAP/SIP).
Solo doctores y admins pueden gestionar fichas prenatales.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.prenatal_visit import (
    PrenatalHistoryResponse,
    PrenatalVisitCreate,
    PrenatalVisitResponse,
)
from app.services import prenatal_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=PrenatalVisitResponse, status_code=201)
async def create_prenatal_visit(
    data: PrenatalVisitCreate,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA)),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un nuevo registro de control prenatal.
    Datos según estándar CLAP/SIP.
    """
    return await prenatal_service.create_visit(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.get("/{visit_id}", response_model=PrenatalVisitResponse)
async def get_prenatal_visit(
    visit_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de una visita prenatal."""
    return await prenatal_service.get_visit(
        db, visit_id=visit_id, clinic_id=user.clinic_id
    )


@router.get("/patient/{patient_id}", response_model=PrenatalHistoryResponse)
async def get_prenatal_history(
    patient_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Historial prenatal completo de una paciente.
    Ordenado por semana gestacional ascendente.
    """
    return await prenatal_service.get_patient_history(
        db, clinic_id=user.clinic_id, patient_id=patient_id
    )
