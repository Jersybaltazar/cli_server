"""
Servicio de informes de imagenología — CRUD básico.

En la Fase 0 se almacenan `findings` como dict genérico y se hereda la
inmutabilidad del MedicalRecord asociado (cuando exista): si el record
padre está firmado, el ImagingReport no puede editarse ni eliminarse.
"""

from datetime import date, datetime, timezone
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.security import decrypt_pii
from app.models.imaging_report import ImagingReport, ImagingStudyType
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.imaging_report import (
    ImagingReportCreate,
    ImagingReportListResponse,
    ImagingReportResponse,
    ImagingReportUpdate,
)
from app.services.audit_service import log_action


# ── Helpers ──────────────────────────────────────────

def _calculate_age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    return relativedelta(date.today(), birth_date).years


def _report_to_response(
    report: ImagingReport,
    patient: Patient | None = None,
) -> ImagingReportResponse:
    """Convierte un ImagingReport a su schema de respuesta con datos derivados."""
    doctor_name = None
    if report.doctor:
        doctor_name = f"{report.doctor.first_name} {report.doctor.last_name}"

    signer_name = None
    if report.signer:
        signer_name = f"{report.signer.first_name} {report.signer.last_name}"

    patient_name = None
    patient_age = None
    patient_document = None
    target_patient = patient or report.patient
    if target_patient:
        patient_name = f"{target_patient.first_name} {target_patient.last_name}"
        patient_age = _calculate_age(target_patient.birth_date)
        try:
            patient_document = decrypt_pii(target_patient.dni)
        except Exception:
            patient_document = None

    return ImagingReportResponse(
        id=report.id,
        clinic_id=report.clinic_id,
        patient_id=report.patient_id,
        doctor_id=report.doctor_id,
        record_id=report.record_id,
        study_type=report.study_type,
        findings=report.findings or {},
        conclusion_items=report.conclusion_items or [],
        recommendations=report.recommendations,
        created_at=report.created_at,
        updated_at=report.updated_at,
        signed_at=report.signed_at,
        signed_by=report.signed_by,
        is_signed=report.is_signed,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_document=patient_document,
        doctor_name=doctor_name,
        signer_name=signer_name,
    )


async def _get_patient_or_404(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> Patient:
    result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundException("Paciente")
    return patient


async def _get_report_or_404(
    db: AsyncSession, clinic_id: UUID, report_id: UUID
) -> ImagingReport:
    result = await db.execute(
        select(ImagingReport)
        .options(
            joinedload(ImagingReport.doctor),
            joinedload(ImagingReport.signer),
            joinedload(ImagingReport.patient),
            joinedload(ImagingReport.record),
            joinedload(ImagingReport.clinic),
        )
        .where(
            ImagingReport.id == report_id,
            ImagingReport.clinic_id == clinic_id,
        )
    )
    report = result.unique().scalar_one_or_none()
    if not report:
        raise NotFoundException("Informe de imagenología")
    return report


def _ensure_mutable(report: ImagingReport) -> None:
    """Bloquea modificaciones si el informe o el MedicalRecord padre están firmados."""
    if report.signed_at is not None:
        raise ForbiddenException(
            "El informe está firmado y no puede modificarse"
        )
    if report.record and report.record.signed_at is not None:
        raise ForbiddenException(
            "El registro clínico asociado está firmado y bloquea este informe"
        )


# ── Crear ────────────────────────────────────────────

async def create_report(
    db: AsyncSession,
    user: User,
    data: ImagingReportCreate,
    ip_address: str | None = None,
) -> ImagingReportResponse:
    clinic_id = user.clinic_id

    patient = await _get_patient_or_404(db, clinic_id, data.patient_id)

    # Si se provee record_id, verificar que pertenece a la clínica y paciente
    if data.record_id is not None:
        record_result = await db.execute(
            select(MedicalRecord).where(
                MedicalRecord.id == data.record_id,
                MedicalRecord.clinic_id == clinic_id,
                MedicalRecord.patient_id == data.patient_id,
            )
        )
        if record_result.scalar_one_or_none() is None:
            raise NotFoundException("Registro médico")

    report = ImagingReport(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        doctor_id=user.id,
        record_id=data.record_id,
        study_type=data.study_type,
        findings=data.findings,
        conclusion_items=data.conclusion_items,
        recommendations=data.recommendations,
    )
    db.add(report)
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="imaging_report",
        entity_id=str(report.id),
        action="create",
        new_data={
            "study_type": data.study_type.value,
            "patient_id": str(data.patient_id),
        },
        ip_address=ip_address,
    )

    # Recargar con relaciones para el response
    report = await _get_report_or_404(db, clinic_id, report.id)
    return _report_to_response(report, patient=patient)


# ── Listar ───────────────────────────────────────────

async def list_reports(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID | None = None,
    study_type: ImagingStudyType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ImagingReportListResponse:
    stmt = (
        select(ImagingReport)
        .options(
            joinedload(ImagingReport.doctor),
            joinedload(ImagingReport.patient),
        )
        .where(ImagingReport.clinic_id == clinic_id)
        .order_by(ImagingReport.created_at.desc())
    )
    if patient_id is not None:
        stmt = stmt.where(ImagingReport.patient_id == patient_id)
    if study_type is not None:
        stmt = stmt.where(ImagingReport.study_type == study_type)
    if date_from is not None:
        stmt = stmt.where(ImagingReport.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ImagingReport.created_at <= date_to)

    result = await db.execute(stmt)
    reports = result.unique().scalars().all()

    return ImagingReportListResponse(
        items=[_report_to_response(r) for r in reports],
        total=len(reports),
    )


# ── Obtener individual ───────────────────────────────

async def get_report(
    db: AsyncSession,
    clinic_id: UUID,
    report_id: UUID,
) -> ImagingReportResponse:
    report = await _get_report_or_404(db, clinic_id, report_id)
    return _report_to_response(report)


async def get_report_raw(
    db: AsyncSession,
    clinic_id: UUID,
    report_id: UUID,
) -> ImagingReport:
    """Devuelve el ORM completo (con relaciones) — usado por el render PDF."""
    return await _get_report_or_404(db, clinic_id, report_id)


# ── Actualizar ───────────────────────────────────────

async def update_report(
    db: AsyncSession,
    user: User,
    report_id: UUID,
    data: ImagingReportUpdate,
    ip_address: str | None = None,
) -> ImagingReportResponse:
    clinic_id = user.clinic_id
    report = await _get_report_or_404(db, clinic_id, report_id)
    _ensure_mutable(report)

    updates: dict = {}
    if data.findings is not None:
        report.findings = data.findings
        updates["findings"] = "updated"
    if data.conclusion_items is not None:
        report.conclusion_items = data.conclusion_items
        updates["conclusion_items"] = data.conclusion_items
    if data.recommendations is not None:
        report.recommendations = data.recommendations
        updates["recommendations"] = data.recommendations

    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="imaging_report",
        entity_id=str(report.id),
        action="update",
        new_data=updates,
        ip_address=ip_address,
    )

    report = await _get_report_or_404(db, clinic_id, report_id)
    return _report_to_response(report)


# ── Firmar (Fase 5) ──────────────────────────────────

async def sign_report(
    db: AsyncSession,
    user: User,
    report_id: UUID,
    ip_address: str | None = None,
) -> ImagingReportResponse:
    """
    Firma digitalmente un informe. Una vez firmado es INMUTABLE.
    Solo el doctor que lo creó (o un SUPER_ADMIN) puede firmarlo.
    """
    clinic_id = user.clinic_id
    report = await _get_report_or_404(db, clinic_id, report_id)

    if report.signed_at is not None:
        raise ForbiddenException("El informe ya está firmado")

    if report.doctor_id != user.id and user.role != UserRole.SUPER_ADMIN:
        raise ForbiddenException(
            "Solo el médico que creó el informe puede firmarlo"
        )

    report.signed_at = datetime.now(timezone.utc)
    report.signed_by = user.id
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="imaging_report",
        entity_id=str(report.id),
        action="sign",
        new_data={"signed_at": report.signed_at.isoformat()},
        ip_address=ip_address,
    )

    report = await _get_report_or_404(db, clinic_id, report_id)
    return _report_to_response(report)


# ── Eliminar ─────────────────────────────────────────

async def delete_report(
    db: AsyncSession,
    user: User,
    report_id: UUID,
    ip_address: str | None = None,
) -> None:
    clinic_id = user.clinic_id
    report = await _get_report_or_404(db, clinic_id, report_id)
    _ensure_mutable(report)

    await db.delete(report)
    await db.flush()

    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="imaging_report",
        entity_id=str(report_id),
        action="delete",
        ip_address=ip_address,
    )
