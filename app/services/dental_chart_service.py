"""
Servicio de odontograma: CRUD de entradas dentales + estado actual completo.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundException
from app.models.dental_chart import DentalChart
from app.models.patient import Patient
from app.models.user import User
from app.schemas.dental_chart import (
    DentalChartCreate,
    DentalChartResponse,
    FullDentalChartResponse,
    ToothStatus,
)
from app.services.audit_service import log_action


# ── Helpers ──────────────────────────────────────────

def _entry_to_response(entry: DentalChart) -> DentalChartResponse:
    """Convierte un modelo DentalChart a su schema de respuesta."""
    doctor_name = None
    if entry.doctor:
        doctor_name = f"{entry.doctor.first_name} {entry.doctor.last_name}"

    return DentalChartResponse(
        id=entry.id,
        clinic_id=entry.clinic_id,
        patient_id=entry.patient_id,
        record_id=entry.record_id,
        doctor_id=entry.doctor_id,
        tooth_number=entry.tooth_number,
        surfaces=entry.surfaces,
        condition=entry.condition,
        treatment=entry.treatment,
        notes=entry.notes,
        doctor_name=doctor_name,
        created_at=entry.created_at,
    )


# ── Crear entrada dental ────────────────────────────

async def create_entry(
    db: AsyncSession,
    user: User,
    data: DentalChartCreate,
    ip_address: str | None = None,
) -> DentalChartResponse:
    """Crea una nueva entrada en el odontograma."""
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

    entry = DentalChart(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        record_id=data.record_id,
        doctor_id=user.id,
        tooth_number=data.tooth_number,
        surfaces=data.surfaces,
        condition=data.condition,
        treatment=data.treatment,
        notes=data.notes,
    )
    db.add(entry)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="dental_chart",
        entity_id=str(entry.id),
        action="create",
        new_data={
            "tooth_number": data.tooth_number,
            "condition": data.condition.value,
            "patient_id": str(data.patient_id),
        },
        ip_address=ip_address,
    )

    # Recargar con relación doctor
    result = await db.execute(
        select(DentalChart)
        .options(joinedload(DentalChart.doctor))
        .where(DentalChart.id == entry.id)
    )
    entry = result.scalar_one()

    return _entry_to_response(entry)


# ── Historial de un diente ───────────────────────────

async def get_tooth_history(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
    tooth_number: int,
) -> list[DentalChartResponse]:
    """Obtiene el historial de tratamientos de un diente específico."""
    result = await db.execute(
        select(DentalChart)
        .options(joinedload(DentalChart.doctor))
        .where(
            DentalChart.patient_id == patient_id,
            DentalChart.clinic_id == clinic_id,
            DentalChart.tooth_number == tooth_number,
        )
        .order_by(DentalChart.created_at.desc())
    )
    entries = result.scalars().unique().all()
    return [_entry_to_response(e) for e in entries]


# ── Odontograma completo ────────────────────────────

async def get_full_chart(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
) -> FullDentalChartResponse:
    """
    Obtiene el estado actual del odontograma completo.
    Para cada diente, retorna la entrada más reciente.
    """
    # Verificar paciente
    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.clinic_id == clinic_id,
        )
    )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    # Obtener todas las entradas del paciente
    result = await db.execute(
        select(DentalChart)
        .where(
            DentalChart.patient_id == patient_id,
            DentalChart.clinic_id == clinic_id,
        )
        .order_by(DentalChart.tooth_number, DentalChart.created_at.desc())
    )
    all_entries = result.scalars().all()

    # Agrupar por diente y tomar el más reciente
    teeth_map: dict[int, list[DentalChart]] = {}
    for entry in all_entries:
        teeth_map.setdefault(entry.tooth_number, []).append(entry)

    teeth: list[ToothStatus] = []
    for tooth_num, entries in sorted(teeth_map.items()):
        latest = entries[0]  # Ya ordenado desc por created_at
        teeth.append(ToothStatus(
            tooth_number=tooth_num,
            condition=latest.condition,
            surfaces=latest.surfaces,
            treatment=latest.treatment,
            last_updated=latest.created_at,
            history_count=len(entries),
        ))

    return FullDentalChartResponse(
        patient_id=patient_id,
        teeth=teeth,
        total_entries=len(all_entries),
    )
