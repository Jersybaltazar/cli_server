"""
Servicio de Historia Clínica Electrónica: creación, consulta y firma.
INSERT-only — los registros firmados son INMUTABLES (NTS 139).
"""

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.medical_record import MedicalRecord, RecordType
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.medical_record import (
    MedicalRecordCreate,
    MedicalRecordListResponse,
    MedicalRecordResponse,
)
from app.models.clinic import Clinic
from app.services.audit_service import log_action
from app.services.organization_service import get_org_clinic_ids


# ── Helpers ──────────────────────────────────────────


async def _get_clinic_org_id(db: AsyncSession, clinic_id: UUID) -> UUID | None:
    """Obtiene el organization_id de una clínica (None si independiente)."""
    result = await db.execute(
        select(Clinic.organization_id).where(Clinic.id == clinic_id)
    )
    return result.scalar_one_or_none()


def _load_options():
    return [
        joinedload(MedicalRecord.patient),
        joinedload(MedicalRecord.doctor),
        joinedload(MedicalRecord.clinic),
    ]


def _record_to_response(record: MedicalRecord) -> MedicalRecordResponse:
    """Convierte un modelo MedicalRecord a su schema de respuesta."""
    patient_name = None
    doctor_name = None
    clinic_name = None

    if record.patient:
        patient_name = f"{record.patient.first_name} {record.patient.last_name}"
    if record.doctor:
        doctor_name = f"{record.doctor.first_name} {record.doctor.last_name}"
    if record.clinic:
        clinic_name = record.clinic.display_name

    return MedicalRecordResponse(
        id=record.id,
        clinic_id=record.clinic_id,
        patient_id=record.patient_id,
        doctor_id=record.doctor_id,
        appointment_id=record.appointment_id,
        record_type=record.record_type,
        cie10_codes=record.cie10_codes,
        content=record.content,
        specialty_data=record.specialty_data,
        notes=record.notes,
        signed_at=record.signed_at,
        signed_by=record.signed_by,
        is_signed=record.is_signed,
        doctor_name=doctor_name,
        patient_name=patient_name,
        clinic_name=clinic_name,
        created_at=record.created_at,
    )


# ── Crear registro clínico ───────────────────────────

async def create_record(
    db: AsyncSession,
    user: User,
    data: MedicalRecordCreate,
    ip_address: str | None = None,
) -> MedicalRecordResponse:
    """
    Crea un nuevo registro clínico.
    Solo doctores y super_admin pueden crear registros.
    """
    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    # Verificar que el paciente existe (cross-sede si tiene org)
    if org_id:
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == data.patient_id,
                Patient.organization_id == org_id,
            )
        )
    else:
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == data.patient_id,
                Patient.clinic_id == clinic_id,
            )
        )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    # Crear registro
    record = MedicalRecord(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        doctor_id=user.id,
        appointment_id=data.appointment_id,
        record_type=data.record_type,
        cie10_codes=data.cie10_codes,
        content=data.content,
        specialty_data=data.specialty_data,
        notes=data.notes,
    )
    db.add(record)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="medical_record",
        entity_id=str(record.id),
        action="create",
        new_data={
            "record_type": data.record_type.value,
            "patient_id": str(data.patient_id),
            "cie10_codes": data.cie10_codes,
        },
        ip_address=ip_address,
    )

    # Recargar con relaciones
    result = await db.execute(
        select(MedicalRecord)
        .options(*_load_options())
        .where(MedicalRecord.id == record.id)
    )
    record = result.scalar_one()

    return _record_to_response(record)


# ── Obtener registro ─────────────────────────────────

async def get_record(
    db: AsyncSession,
    record_id: UUID,
    user: User,
) -> MedicalRecordResponse:
    """
    Obtiene un registro clínico por ID.
    Receptionist NO puede ver HCE (NTS 139 Cap. VII).
    """
    if user.role == UserRole.RECEPTIONIST:
        raise ForbiddenException("Recepcionistas no tienen acceso a historias clínicas")

    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    query = select(MedicalRecord).options(*_load_options()).where(
        MedicalRecord.id == record_id,
    )

    if org_id:
        # Cross-sede: permitir lectura si pertenece a cualquier sede de la org
        org_clinic_ids = await get_org_clinic_ids(db, org_id)
        query = query.where(MedicalRecord.clinic_id.in_(org_clinic_ids))
    else:
        query = query.where(MedicalRecord.clinic_id == clinic_id)

    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record:
        raise NotFoundException("Registro clínico")

    return _record_to_response(record)


# ── Historial del paciente ───────────────────────────

async def list_patient_records(
    db: AsyncSession,
    user: User,
    patient_id: UUID,
    *,
    page: int = 1,
    size: int = 20,
    record_type: RecordType | None = None,
) -> MedicalRecordListResponse:
    """
    Lista el historial clínico de un paciente.
    Receptionist NO puede ver HCE.
    """
    if user.role == UserRole.RECEPTIONIST:
        raise ForbiddenException("Recepcionistas no tienen acceso a historias clínicas")

    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    query = (
        select(MedicalRecord)
        .options(*_load_options())
        .where(MedicalRecord.patient_id == patient_id)
    )

    if org_id:
        # Cross-sede: registros de todas las sedes de la org
        org_clinic_ids = await get_org_clinic_ids(db, org_id)
        query = query.where(MedicalRecord.clinic_id.in_(org_clinic_ids))
    else:
        query = query.where(MedicalRecord.clinic_id == clinic_id)

    if record_type:
        query = query.where(MedicalRecord.record_type == record_type)

    # Count total
    count_query = select(func.count()).select_from(
        query.with_only_columns(MedicalRecord.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginación (más recientes primero)
    offset = (page - 1) * size
    query = query.order_by(MedicalRecord.created_at.desc())
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    records = result.scalars().unique().all()

    return MedicalRecordListResponse(
        items=[_record_to_response(r) for r in records],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


# ── Firma digital ────────────────────────────────────

async def sign_record(
    db: AsyncSession,
    record_id: UUID,
    user: User,
    ip_address: str | None = None,
) -> MedicalRecordResponse:
    """
    Firma un registro clínico. Una vez firmado, es INMUTABLE.
    Solo el doctor que creó el registro puede firmarlo.
    """
    result = await db.execute(
        select(MedicalRecord)
        .options(*_load_options())
        .where(
            MedicalRecord.id == record_id,
            MedicalRecord.clinic_id == user.clinic_id,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise NotFoundException("Registro clínico")

    if record.is_signed:
        raise ValidationException("El registro ya está firmado y no puede modificarse")

    if record.doctor_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise ForbiddenException("Solo el doctor que creó el registro puede firmarlo")

    record.signed_at = datetime.now(timezone.utc)
    record.signed_by = user.id
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="medical_record",
        entity_id=str(record.id),
        action="sign",
        new_data={"signed_at": record.signed_at.isoformat()},
        ip_address=ip_address,
    )

    return _record_to_response(record)
