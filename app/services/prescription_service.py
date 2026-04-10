"""
Servicio de recetas médicas (prescriptions) — CRUD + firma digital.

Patrón: análogo a imaging_service. Receta = encabezado + items.
Inmutabilidad post-firma; opcionalmente heredada del MedicalRecord padre.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.security import decrypt_pii, generate_verification_token
from app.models.clinic import Clinic
from app.models.medical_record import MedicalRecord
from app.models.medication_catalog import MedicationCatalog
from app.models.patient import Patient
from app.models.prescription import (
    Prescription,
    PrescriptionItem,
    PrescriptionTemplate,
)
from app.models.user import User, UserRole
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionItemResponse,
    PrescriptionListResponse,
    PrescriptionResponse,
    PrescriptionTemplateCreate,
    PrescriptionTemplateListResponse,
    PrescriptionTemplateResponse,
    PrescriptionUpdate,
)
from app.services.audit_service import log_action
from app.services.prescription_sequence_service import next_serial


# ── Helpers ──────────────────────────────────────────

def _calculate_age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    return relativedelta(date.today(), birth_date).years


def _item_to_response(item: PrescriptionItem) -> PrescriptionItemResponse:
    return PrescriptionItemResponse(
        id=item.id,
        position=item.position,
        medication_id=item.medication_id,
        medication=item.medication,
        presentation=item.presentation,
        dose=item.dose,
        frequency=item.frequency,
        duration=item.duration,
        quantity=item.quantity,
        instructions=item.instructions,
    )


def _to_response(
    rx: Prescription,
    patient: Patient | None = None,
) -> PrescriptionResponse:
    doctor_name = (
        f"{rx.doctor.first_name} {rx.doctor.last_name}" if rx.doctor else None
    )
    doctor_cmp = rx.doctor.cmp_number if rx.doctor else None
    doctor_authorization_number = (
        rx.doctor.controlled_authorization_number if rx.doctor else None
    )
    signer_name = (
        f"{rx.signer.first_name} {rx.signer.last_name}" if rx.signer else None
    )

    target = patient or rx.patient
    patient_name = None
    patient_age = None
    patient_document = None
    patient_address = None
    if target:
        patient_name = f"{target.first_name} {target.last_name}"
        patient_age = _calculate_age(target.birth_date)
        patient_address = target.address
        try:
            patient_document = decrypt_pii(target.dni)
        except Exception:
            patient_document = None

    return PrescriptionResponse(
        id=rx.id,
        clinic_id=rx.clinic_id,
        patient_id=rx.patient_id,
        doctor_id=rx.doctor_id,
        record_id=rx.record_id,
        diagnosis=rx.diagnosis,
        cie10_code=rx.cie10_code,
        notes=rx.notes,
        serial_number=rx.serial_number,
        kind=rx.kind or "common",
        valid_until=rx.valid_until,
        verification_token=rx.verification_token,
        items=[_item_to_response(i) for i in rx.items],
        created_at=rx.created_at,
        updated_at=rx.updated_at,
        signed_at=rx.signed_at,
        signed_by=rx.signed_by,
        is_signed=rx.is_signed,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_document=patient_document,
        patient_address=patient_address,
        doctor_name=doctor_name,
        doctor_cmp=doctor_cmp,
        doctor_authorization_number=doctor_authorization_number,
        signer_name=signer_name,
    )


# ── Detección de tipo de receta (Fase 2.3) ──────────

async def _detect_kind(
    db: AsyncSession, items: list[PrescriptionItem]
) -> str:
    """
    Devuelve 'controlled' si algún item está vinculado a un medicamento
    del catálogo marcado como controlado. Los ítems de texto libre
    (sin medication_id) no pueden ser detectados automáticamente.
    """
    ids = [i.medication_id for i in items if i.medication_id is not None]
    if not ids:
        return "common"
    result = await db.execute(
        select(MedicationCatalog.id).where(
            MedicationCatalog.id.in_(ids),
            MedicationCatalog.is_controlled.is_(True),
        )
    )
    if result.first() is not None:
        return "controlled"
    return "common"


async def _get_patient_or_404(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> Patient:
    """
    Obtiene un paciente visible desde la clínica actual.

    Soporta el modelo cross-sede: si la clínica pertenece a una
    organización, se permite cualquier paciente de la misma org
    (su `clinic_id` puede apuntar a la sede donde fue creado
    originalmente, mientras esté enlazado vía patient_clinic_links).
    """
    org_result = await db.execute(
        select(Clinic.organization_id).where(Clinic.id == clinic_id)
    )
    org_id = org_result.scalar_one_or_none()

    if org_id:
        stmt = select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == org_id,
        )
    else:
        stmt = select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )

    result = await db.execute(stmt)
    p = result.scalar_one_or_none()
    if not p:
        raise NotFoundException("Paciente")
    return p


async def _get_or_404(
    db: AsyncSession, clinic_id: UUID, rx_id: UUID
) -> Prescription:
    result = await db.execute(
        select(Prescription)
        .options(
            joinedload(Prescription.doctor),
            joinedload(Prescription.signer),
            joinedload(Prescription.patient),
            joinedload(Prescription.record),
            joinedload(Prescription.clinic),
            selectinload(Prescription.items),
        )
        .where(
            Prescription.id == rx_id,
            Prescription.clinic_id == clinic_id,
        )
    )
    rx = result.unique().scalar_one_or_none()
    if not rx:
        raise NotFoundException("Receta")
    return rx


def _ensure_mutable(rx: Prescription) -> None:
    if rx.signed_at is not None:
        raise ForbiddenException("La receta está firmada y no puede modificarse")
    if rx.record and rx.record.signed_at is not None:
        raise ForbiddenException(
            "El registro clínico asociado está firmado y bloquea esta receta"
        )


# ── Crear ────────────────────────────────────────────

async def create_prescription(
    db: AsyncSession,
    user: User,
    data: PrescriptionCreate,
    ip_address: str | None = None,
) -> PrescriptionResponse:
    clinic_id = user.clinic_id
    patient = await _get_patient_or_404(db, clinic_id, data.patient_id)

    if data.record_id is not None:
        rec_q = await db.execute(
            select(MedicalRecord).where(
                MedicalRecord.id == data.record_id,
                MedicalRecord.clinic_id == clinic_id,
                MedicalRecord.patient_id == data.patient_id,
            )
        )
        if rec_q.scalar_one_or_none() is None:
            raise NotFoundException("Registro médico")

    rx = Prescription(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        doctor_id=user.id,
        record_id=data.record_id,
        diagnosis=data.diagnosis,
        cie10_code=data.cie10_code,
        notes=data.notes,
    )
    for idx, it in enumerate(data.items):
        rx.items.append(
            PrescriptionItem(
                position=idx,
                medication_id=it.medication_id,
                medication=it.medication,
                presentation=it.presentation,
                dose=it.dose,
                frequency=it.frequency,
                duration=it.duration,
                quantity=it.quantity,
                instructions=it.instructions,
            )
        )

    # Fase 2.3 — auto-detección de receta controlada
    rx.kind = await _detect_kind(db, rx.items)

    db.add(rx)
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="prescription",
        entity_id=str(rx.id),
        action="create",
        new_data={
            "patient_id": str(data.patient_id),
            "items": len(data.items),
        },
        ip_address=ip_address,
    )

    rx = await _get_or_404(db, clinic_id, rx.id)
    return _to_response(rx, patient=patient)


# ── Listar ───────────────────────────────────────────

async def list_prescriptions(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PrescriptionListResponse:
    stmt = (
        select(Prescription)
        .options(
            joinedload(Prescription.doctor),
            joinedload(Prescription.patient),
            joinedload(Prescription.signer),
            selectinload(Prescription.items),
        )
        .where(Prescription.clinic_id == clinic_id)
        .order_by(Prescription.created_at.desc())
    )
    if patient_id is not None:
        stmt = stmt.where(Prescription.patient_id == patient_id)
    if date_from is not None:
        stmt = stmt.where(Prescription.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Prescription.created_at <= date_to)

    result = await db.execute(stmt)
    rows = result.unique().scalars().all()

    return PrescriptionListResponse(
        items=[_to_response(r) for r in rows],
        total=len(rows),
    )


# ── Obtener ──────────────────────────────────────────

async def get_prescription(
    db: AsyncSession, clinic_id: UUID, rx_id: UUID
) -> PrescriptionResponse:
    rx = await _get_or_404(db, clinic_id, rx_id)
    return _to_response(rx)


async def get_prescription_raw(
    db: AsyncSession, clinic_id: UUID, rx_id: UUID
) -> Prescription:
    return await _get_or_404(db, clinic_id, rx_id)


# ── Actualizar ───────────────────────────────────────

async def update_prescription(
    db: AsyncSession,
    user: User,
    rx_id: UUID,
    data: PrescriptionUpdate,
    ip_address: str | None = None,
) -> PrescriptionResponse:
    clinic_id = user.clinic_id
    rx = await _get_or_404(db, clinic_id, rx_id)
    _ensure_mutable(rx)

    if data.diagnosis is not None:
        rx.diagnosis = data.diagnosis
    if data.cie10_code is not None:
        rx.cie10_code = data.cie10_code
    if data.notes is not None:
        rx.notes = data.notes
    if data.items is not None:
        rx.items.clear()
        await db.flush()
        for idx, it in enumerate(data.items):
            rx.items.append(
                PrescriptionItem(
                    position=idx,
                    medication_id=it.medication_id,
                    medication=it.medication,
                    presentation=it.presentation,
                    dose=it.dose,
                    frequency=it.frequency,
                    duration=it.duration,
                    quantity=it.quantity,
                    instructions=it.instructions,
                )
            )
        # Fase 2.3 — re-detectar tipo si cambiaron los items
        rx.kind = await _detect_kind(db, rx.items)

    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="prescription",
        entity_id=str(rx.id),
        action="update",
        ip_address=ip_address,
    )

    rx = await _get_or_404(db, clinic_id, rx_id)
    return _to_response(rx)


# ── Firmar ───────────────────────────────────────────

async def sign_prescription(
    db: AsyncSession,
    user: User,
    rx_id: UUID,
    ip_address: str | None = None,
    acknowledged_interactions: list[dict] | None = None,
) -> PrescriptionResponse:
    clinic_id = user.clinic_id
    rx = await _get_or_404(db, clinic_id, rx_id)

    if rx.signed_at is not None:
        raise ForbiddenException("La receta ya está firmada")
    if rx.doctor_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise ForbiddenException("Solo el médico que creó la receta puede firmarla")

    # ── Validaciones específicas para recetas controladas (Fase 2.3) ──
    if rx.kind == "controlled":
        # Médico autorizado por DIGEMID
        if not user.is_authorized_controlled:
            raise ForbiddenException(
                "No está autorizado a prescribir sustancias controladas. "
                "Contacte al administrador de su clínica."
            )
        expiry = user.controlled_authorization_expiry
        if expiry is not None and expiry < date.today():
            raise ForbiddenException(
                "Su autorización DIGEMID para controlados está vencida. "
                "Contacte al administrador de su clínica."
            )
        # Dirección del paciente es obligatoria (DS 014-2011-SA)
        if not (rx.patient and rx.patient.address and rx.patient.address.strip()):
            raise ForbiddenException(
                "Falta dirección del paciente. Edite la ficha del paciente "
                "antes de firmar una receta controlada."
            )

    if rx.serial_number is None:
        rx.serial_number = await next_serial(
            db, clinic_id=clinic_id, kind=rx.kind or "common"
        )
    rx.signed_at = datetime.now(timezone.utc)
    rx.signed_by = user.id

    # Vigencia: 3 días para controladas; las comunes no tienen vigencia oficial
    if rx.kind == "controlled":
        rx.valid_until = rx.signed_at.date() + timedelta(days=3)

    # Fase 2.4 — registrar interacciones aceptadas (auditoría DDI)
    if acknowledged_interactions:
        rx.acknowledged_interactions = acknowledged_interactions

    # Fase 2.5 — generar token de verificación QR
    if rx.verification_token is None:
        rx.verification_token = generate_verification_token(str(rx.id))

    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="prescription",
        entity_id=str(rx.id),
        action="sign",
        new_data={
            "signed_at": rx.signed_at.isoformat(),
            "serial_number": rx.serial_number,
        },
        ip_address=ip_address,
    )

    rx = await _get_or_404(db, clinic_id, rx_id)
    return _to_response(rx)


# ── Eliminar ─────────────────────────────────────────

async def delete_prescription(
    db: AsyncSession,
    user: User,
    rx_id: UUID,
    ip_address: str | None = None,
) -> None:
    clinic_id = user.clinic_id
    rx = await _get_or_404(db, clinic_id, rx_id)
    _ensure_mutable(rx)

    await db.delete(rx)
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="prescription",
        entity_id=str(rx_id),
        action="delete",
        ip_address=ip_address,
    )


# ══════════════════════════════════════════════════════
# Plantillas (recetas frecuentes)
# ══════════════════════════════════════════════════════

def _tpl_to_response(tpl: PrescriptionTemplate) -> PrescriptionTemplateResponse:
    creator_name = None
    if tpl.creator:
        creator_name = f"{tpl.creator.first_name} {tpl.creator.last_name}"
    return PrescriptionTemplateResponse(
        id=tpl.id,
        clinic_id=tpl.clinic_id,
        created_by=tpl.created_by,
        name=tpl.name,
        diagnosis=tpl.diagnosis,
        cie10_code=tpl.cie10_code,
        notes=tpl.notes,
        items=tpl.items or [],
        created_at=tpl.created_at,
        creator_name=creator_name,
    )


async def _get_tpl_or_404(
    db: AsyncSession, clinic_id: UUID, template_id: UUID
) -> PrescriptionTemplate:
    result = await db.execute(
        select(PrescriptionTemplate)
        .options(joinedload(PrescriptionTemplate.creator))
        .where(
            PrescriptionTemplate.id == template_id,
            PrescriptionTemplate.clinic_id == clinic_id,
        )
    )
    tpl = result.unique().scalar_one_or_none()
    if not tpl:
        raise NotFoundException("Plantilla de receta")
    return tpl


async def list_templates(
    db: AsyncSession, clinic_id: UUID
) -> PrescriptionTemplateListResponse:
    result = await db.execute(
        select(PrescriptionTemplate)
        .options(joinedload(PrescriptionTemplate.creator))
        .where(PrescriptionTemplate.clinic_id == clinic_id)
        .order_by(PrescriptionTemplate.created_at.desc())
    )
    rows = result.unique().scalars().all()
    return PrescriptionTemplateListResponse(
        items=[_tpl_to_response(t) for t in rows],
        total=len(rows),
    )


async def create_template(
    db: AsyncSession,
    user: User,
    data: PrescriptionTemplateCreate,
    ip_address: str | None = None,
) -> PrescriptionTemplateResponse:
    tpl = PrescriptionTemplate(
        clinic_id=user.clinic_id,
        created_by=user.id,
        name=data.name.strip(),
        diagnosis=data.diagnosis,
        cie10_code=data.cie10_code,
        notes=data.notes,
        items=[i.model_dump() for i in data.items],
    )
    db.add(tpl)
    await db.flush()

    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="prescription_template",
        entity_id=str(tpl.id),
        action="create",
        new_data={"name": tpl.name},
        ip_address=ip_address,
    )

    tpl = await _get_tpl_or_404(db, user.clinic_id, tpl.id)
    return _tpl_to_response(tpl)


async def delete_template(
    db: AsyncSession,
    user: User,
    template_id: UUID,
    ip_address: str | None = None,
) -> None:
    tpl = await _get_tpl_or_404(db, user.clinic_id, template_id)
    await db.delete(tpl)
    await db.flush()

    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="prescription_template",
        entity_id=str(template_id),
        action="delete",
        ip_address=ip_address,
    )
