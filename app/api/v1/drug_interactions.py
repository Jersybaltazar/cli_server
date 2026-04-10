"""
Endpoints REST para detección de interacciones medicamentosas (DDI).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.drug_interaction import DDICheckRequest, DDICheckResponse
from app.services import drug_interaction_service

router = APIRouter()

_CLINICAL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)


@router.post("/check", response_model=DDICheckResponse)
async def check_drug_interactions(
    data: DDICheckRequest,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifica interacciones medicamentosas para un conjunto de items.

    Compara intra-receta + contra recetas activas (firmadas, <30 días)
    del mismo paciente.
    """
    items = [
        {
            "index": idx,
            "medication": it.medication,
            "medication_id": it.medication_id,
        }
        for idx, it in enumerate(data.items)
    ]
    return await drug_interaction_service.check_interactions(
        db,
        patient_id=data.patient_id,
        items=items,
        exclude_prescription_id=data.exclude_prescription_id,
    )
