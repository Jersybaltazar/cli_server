"""
Endpoints para gestión de vacunación.
Esquemas de vacunas + registro de dosis por paciente.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.vaccination import (
    PatientVaccinationCreate,
    PatientVaccinationHistory,
    PatientVaccinationResponse,
    VaccineSchemeCreate,
    VaccineSchemeResponse,
    VaccineSchemeUpdate,
)
from app.services import vaccination_service

router = APIRouter()

_ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)
_CLINICAL_ROLES = (
    UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR, UserRole.OBSTETRA,
)


# ── VaccineScheme CRUD ─────────────────────────────────

@router.post("/schemes", response_model=VaccineSchemeResponse, status_code=201)
async def create_vaccine_scheme(
    data: VaccineSchemeCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un esquema de vacuna. Solo admin."""
    return await vaccination_service.create_vaccine_scheme(db, data=data)


@router.get("/schemes", response_model=list[VaccineSchemeResponse])
async def list_vaccine_schemes(
    active_only: bool = Query(True),
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista esquemas de vacunas disponibles."""
    return await vaccination_service.list_vaccine_schemes(db, active_only=active_only)


@router.patch("/schemes/{scheme_id}", response_model=VaccineSchemeResponse)
async def update_vaccine_scheme(
    scheme_id: UUID,
    data: VaccineSchemeUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un esquema de vacuna. Solo admin."""
    return await vaccination_service.update_vaccine_scheme(db, scheme_id=scheme_id, data=data)


# ── Registro de dosis ──────────────────────────────────

@router.post("/doses", response_model=PatientVaccinationResponse, status_code=201)
async def register_dose(
    data: PatientVaccinationCreate,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Registra una dosis de vacuna para un paciente."""
    vacc = await vaccination_service.register_dose(
        db, clinic_id=user.clinic_id, user_id=user.id, data=data
    )
    # Retornar con datos enriquecidos
    from app.models.vaccination import VaccineScheme
    from sqlalchemy import select
    scheme = await db.scalar(select(VaccineScheme).where(VaccineScheme.id == vacc.vaccine_scheme_id))

    return PatientVaccinationResponse(
        id=vacc.id,
        clinic_id=vacc.clinic_id,
        patient_id=vacc.patient_id,
        vaccine_scheme_id=vacc.vaccine_scheme_id,
        dose_number=vacc.dose_number,
        administered_at=vacc.administered_at,
        administered_by=vacc.administered_by,
        lot_number=vacc.lot_number,
        next_dose_date=vacc.next_dose_date,
        inventory_item_id=vacc.inventory_item_id,
        notes=vacc.notes,
        created_at=vacc.created_at,
        vaccine_name=scheme.name if scheme else None,
        administrator_name=f"{user.first_name} {user.last_name}",
    )


# ── Historial de paciente ─────────────────────────────

@router.get("/patients/{patient_id}", response_model=PatientVaccinationHistory)
async def get_patient_vaccination_history(
    patient_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Historial de vacunación de un paciente con dosis pendientes."""
    return await vaccination_service.get_patient_vaccination_history(
        db, clinic_id=user.clinic_id, patient_id=patient_id
    )


# ── Vacunas vencidas ──────────────────────────────────

@router.get("/overdue", response_model=list[dict])
async def list_overdue_vaccinations(
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista pacientes con vacunas vencidas (dosis pendientes pasadas de fecha)."""
    return await vaccination_service.list_overdue_vaccinations(
        db, clinic_id=user.clinic_id
    )
