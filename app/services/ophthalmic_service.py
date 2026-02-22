"""
Servicio de exámenes oftalmológicos: CRUD + historial por paciente.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundException
from app.models.ophthalmic_exam import EyeSide, OphthalmicExam
from app.models.patient import Patient
from app.models.user import User
from app.schemas.ophthalmic_exam import (
    OphthalmicExamCreate,
    OphthalmicExamResponse,
    OphthalmicHistoryResponse,
)
from app.services.audit_service import log_action


# ── Helpers ──────────────────────────────────────────

def _exam_to_response(exam: OphthalmicExam) -> OphthalmicExamResponse:
    """Convierte un modelo OphthalmicExam a su schema de respuesta."""
    doctor_name = None
    if exam.doctor:
        doctor_name = f"{exam.doctor.first_name} {exam.doctor.last_name}"

    return OphthalmicExamResponse(
        id=exam.id,
        clinic_id=exam.clinic_id,
        patient_id=exam.patient_id,
        record_id=exam.record_id,
        doctor_id=exam.doctor_id,
        eye=exam.eye,
        visual_acuity_uncorrected=exam.visual_acuity_uncorrected,
        visual_acuity_corrected=exam.visual_acuity_corrected,
        sphere=exam.sphere,
        cylinder=exam.cylinder,
        axis=exam.axis,
        addition=exam.addition,
        iop=exam.iop,
        extra_data=exam.extra_data,
        notes=exam.notes,
        doctor_name=doctor_name,
        created_at=exam.created_at,
    )


# ── Crear examen ─────────────────────────────────────

async def create_exam(
    db: AsyncSession,
    user: User,
    data: OphthalmicExamCreate,
    ip_address: str | None = None,
) -> OphthalmicExamResponse:
    """Crea un nuevo examen oftalmológico."""
    clinic_id = user.clinic_id

    # Verificar que el paciente existe
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == data.patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    exam = OphthalmicExam(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        record_id=data.record_id,
        doctor_id=user.id,
        eye=data.eye,
        visual_acuity_uncorrected=data.visual_acuity_uncorrected,
        visual_acuity_corrected=data.visual_acuity_corrected,
        sphere=data.sphere,
        cylinder=data.cylinder,
        axis=data.axis,
        addition=data.addition,
        iop=data.iop,
        extra_data=data.extra_data,
        notes=data.notes,
    )
    db.add(exam)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="ophthalmic_exam",
        entity_id=str(exam.id),
        action="create",
        new_data={
            "eye": data.eye.value,
            "patient_id": str(data.patient_id),
            "iop": data.iop,
        },
        ip_address=ip_address,
    )

    # Recargar con relación doctor
    result = await db.execute(
        select(OphthalmicExam)
        .options(joinedload(OphthalmicExam.doctor))
        .where(OphthalmicExam.id == exam.id)
    )
    exam = result.scalar_one()

    return _exam_to_response(exam)


# ── Obtener examen individual ────────────────────────

async def get_exam(
    db: AsyncSession,
    exam_id: UUID,
    clinic_id: UUID,
) -> OphthalmicExamResponse:
    """Obtiene un examen oftalmológico por ID."""
    result = await db.execute(
        select(OphthalmicExam)
        .options(joinedload(OphthalmicExam.doctor))
        .where(
            OphthalmicExam.id == exam_id,
            OphthalmicExam.clinic_id == clinic_id,
        )
    )
    exam = result.scalar_one_or_none()

    if not exam:
        raise NotFoundException("Examen oftalmológico")

    return _exam_to_response(exam)


# ── Historial del paciente ───────────────────────────

async def get_patient_history(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
    *,
    eye: EyeSide | None = None,
) -> OphthalmicHistoryResponse:
    """Obtiene el historial oftalmológico completo de un paciente."""
    # Verificar paciente
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    query = (
        select(OphthalmicExam)
        .options(joinedload(OphthalmicExam.doctor))
        .where(
            OphthalmicExam.patient_id == patient_id,
            OphthalmicExam.clinic_id == clinic_id,
        )
    )

    if eye:
        query = query.where(OphthalmicExam.eye == eye)

    query = query.order_by(OphthalmicExam.created_at.desc())

    result = await db.execute(query)
    exams = result.scalars().unique().all()

    return OphthalmicHistoryResponse(
        patient_id=patient_id,
        exams=[_exam_to_response(e) for e in exams],
        total_exams=len(exams),
    )
