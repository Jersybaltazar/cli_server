"""
Endpoints de exámenes oftalmológicos.
Solo doctores y admins pueden gestionar fichas oftalmológicas.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.ophthalmic_exam import EyeSide
from app.models.user import User, UserRole
from app.schemas.ophthalmic_exam import (
    OphthalmicExamCreate,
    OphthalmicExamResponse,
    OphthalmicHistoryResponse,
)
from app.services import ophthalmic_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=OphthalmicExamResponse, status_code=201)
async def create_ophthalmic_exam(
    data: OphthalmicExamCreate,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un nuevo examen oftalmológico.
    Incluye refracción, PIO y agudeza visual por ojo (OD/OS).
    """
    return await ophthalmic_service.create_exam(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.get("/{exam_id}", response_model=OphthalmicExamResponse)
async def get_ophthalmic_exam(
    exam_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR
    )),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un examen oftalmológico."""
    return await ophthalmic_service.get_exam(
        db, exam_id=exam_id, clinic_id=user.clinic_id
    )


@router.get("/patient/{patient_id}", response_model=OphthalmicHistoryResponse)
async def get_ophthalmic_history(
    patient_id: UUID,
    eye: EyeSide | None = Query(None, description="Filtrar por ojo: OD u OS"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Historial oftalmológico completo de un paciente.
    Opcionalmente filtrar por ojo (OD / OS).
    """
    return await ophthalmic_service.get_patient_history(
        db, clinic_id=user.clinic_id, patient_id=patient_id, eye=eye
    )
