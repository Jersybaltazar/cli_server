"""
Servicio de control prenatal: CRUD de visitas + historial completo.
Estándar CLAP/SIP.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundException
from app.models.patient import Patient
from app.models.prenatal_visit import PrenatalVisit
from app.models.user import User
from app.schemas.prenatal_visit import (
    PrenatalHistoryResponse,
    PrenatalVisitCreate,
    PrenatalVisitResponse,
)
from app.services.audit_service import log_action


# ── Helpers ──────────────────────────────────────────

def _visit_to_response(visit: PrenatalVisit) -> PrenatalVisitResponse:
    """Convierte un modelo PrenatalVisit a su schema de respuesta."""
    doctor_name = None
    if visit.doctor:
        doctor_name = f"{visit.doctor.first_name} {visit.doctor.last_name}"

    return PrenatalVisitResponse(
        id=visit.id,
        clinic_id=visit.clinic_id,
        patient_id=visit.patient_id,
        record_id=visit.record_id,
        doctor_id=visit.doctor_id,
        gestational_week=visit.gestational_week,
        weight=visit.weight,
        blood_pressure_systolic=visit.blood_pressure_systolic,
        blood_pressure_diastolic=visit.blood_pressure_diastolic,
        blood_pressure=visit.blood_pressure,
        uterine_height=visit.uterine_height,
        fetal_heart_rate=visit.fetal_heart_rate,
        presentation=visit.presentation,
        fetal_movements=visit.fetal_movements,
        edema=visit.edema,
        labs=visit.labs,
        notes=visit.notes,
        next_appointment_notes=visit.next_appointment_notes,
        doctor_name=doctor_name,
        created_at=visit.created_at,
    )


# ── Crear visita prenatal ────────────────────────────

async def create_visit(
    db: AsyncSession,
    user: User,
    data: PrenatalVisitCreate,
    ip_address: str | None = None,
) -> PrenatalVisitResponse:
    """Crea un nuevo registro de control prenatal."""
    clinic_id = user.clinic_id

    # Verificar que la paciente existe
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == data.patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    visit = PrenatalVisit(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        record_id=data.record_id,
        doctor_id=user.id,
        gestational_week=data.gestational_week,
        weight=data.weight,
        blood_pressure_systolic=data.blood_pressure_systolic,
        blood_pressure_diastolic=data.blood_pressure_diastolic,
        uterine_height=data.uterine_height,
        fetal_heart_rate=data.fetal_heart_rate,
        presentation=data.presentation,
        fetal_movements=data.fetal_movements,
        edema=data.edema,
        labs=data.labs,
        notes=data.notes,
        next_appointment_notes=data.next_appointment_notes,
    )
    db.add(visit)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="prenatal_visit",
        entity_id=str(visit.id),
        action="create",
        new_data={
            "gestational_week": data.gestational_week,
            "patient_id": str(data.patient_id),
        },
        ip_address=ip_address,
    )

    # Recargar con relación doctor
    result = await db.execute(
        select(PrenatalVisit)
        .options(joinedload(PrenatalVisit.doctor))
        .where(PrenatalVisit.id == visit.id)
    )
    visit = result.scalar_one()

    return _visit_to_response(visit)


# ── Obtener visita individual ────────────────────────

async def get_visit(
    db: AsyncSession,
    visit_id: UUID,
    clinic_id: UUID,
) -> PrenatalVisitResponse:
    """Obtiene una visita prenatal por ID."""
    result = await db.execute(
        select(PrenatalVisit)
        .options(joinedload(PrenatalVisit.doctor))
        .where(
            PrenatalVisit.id == visit_id,
            PrenatalVisit.clinic_id == clinic_id,
        )
    )
    visit = result.scalar_one_or_none()

    if not visit:
        raise NotFoundException("Visita prenatal")

    return _visit_to_response(visit)


# ── Historial prenatal completo ──────────────────────

async def get_patient_history(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
) -> PrenatalHistoryResponse:
    """Obtiene el historial prenatal completo de una paciente."""
    # Verificar paciente
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    result = await db.execute(
        select(PrenatalVisit)
        .options(joinedload(PrenatalVisit.doctor))
        .where(
            PrenatalVisit.patient_id == patient_id,
            PrenatalVisit.clinic_id == clinic_id,
        )
        .order_by(PrenatalVisit.gestational_week.asc())
    )
    visits = result.scalars().unique().all()

    return PrenatalHistoryResponse(
        patient_id=patient_id,
        visits=[_visit_to_response(v) for v in visits],
        total_visits=len(visits),
    )
