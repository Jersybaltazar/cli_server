"""
Servicio de Vacunación — CRUD esquemas, registro de dosis, historial.
"""

import logging
from datetime import date, datetime, timezone
from dateutil.relativedelta import relativedelta
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, ValidationException
from app.models.vaccination import VaccineScheme, PatientVaccination
from app.models.user import User
from app.schemas.vaccination import (
    VaccineSchemeCreate,
    VaccineSchemeUpdate,
    PatientVaccinationCreate,
    PatientVaccinationResponse,
    PatientVaccinationHistory,
)

logger = logging.getLogger(__name__)


# ── VaccineScheme CRUD ─────────────────────────────────


async def create_vaccine_scheme(
    db: AsyncSession, data: VaccineSchemeCreate
) -> VaccineScheme:
    """Crea un nuevo esquema de vacuna."""
    if len(data.dose_intervals_months) != data.doses_total:
        raise ValidationException(
            f"dose_intervals_months debe tener {data.doses_total} elementos"
        )
    scheme = VaccineScheme(**data.model_dump())
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def list_vaccine_schemes(
    db: AsyncSession, active_only: bool = True
) -> list[VaccineScheme]:
    """Lista esquemas de vacunas."""
    query = select(VaccineScheme).order_by(VaccineScheme.name)
    if active_only:
        query = query.where(VaccineScheme.is_active.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_vaccine_scheme(
    db: AsyncSession, scheme_id: UUID, data: VaccineSchemeUpdate
) -> VaccineScheme:
    """Actualiza un esquema de vacuna."""
    result = await db.execute(
        select(VaccineScheme).where(VaccineScheme.id == scheme_id)
    )
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise NotFoundException("Esquema de vacuna no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scheme, key, value)

    await db.commit()
    await db.refresh(scheme)
    return scheme


# ── PatientVaccination ─────────────────────────────────


async def register_dose(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    data: PatientVaccinationCreate,
) -> PatientVaccination:
    """Registra una dosis de vacuna para un paciente."""
    # Validar esquema
    scheme_result = await db.execute(
        select(VaccineScheme).where(VaccineScheme.id == data.vaccine_scheme_id)
    )
    scheme = scheme_result.scalar_one_or_none()
    if not scheme:
        raise NotFoundException("Esquema de vacuna no encontrado")

    if data.dose_number > scheme.doses_total:
        raise ValidationException(
            f"El esquema {scheme.name} solo tiene {scheme.doses_total} dosis"
        )

    # Calcular next_dose_date
    next_dose_date = None
    if data.dose_number < scheme.doses_total:
        intervals = scheme.dose_intervals_months
        if data.dose_number < len(intervals):
            next_interval = intervals[data.dose_number]  # intervalo para la siguiente dosis
            current_interval = intervals[data.dose_number - 1]
            months_until_next = next_interval - current_interval
            next_dose_date = (
                date.today() + relativedelta(months=months_until_next)
            )

    vaccination = PatientVaccination(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        vaccine_scheme_id=data.vaccine_scheme_id,
        dose_number=data.dose_number,
        administered_by=user_id,
        administered_at=datetime.now(timezone.utc),
        lot_number=data.lot_number,
        next_dose_date=next_dose_date,
        inventory_item_id=data.inventory_item_id,
        notes=data.notes,
    )
    db.add(vaccination)
    await db.commit()
    await db.refresh(vaccination)
    return vaccination


async def get_patient_vaccination_history(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID,
) -> PatientVaccinationHistory:
    """Obtiene historial completo de vacunación de un paciente."""
    result = await db.execute(
        select(PatientVaccination)
        .where(
            PatientVaccination.clinic_id == clinic_id,
            PatientVaccination.patient_id == patient_id,
        )
        .options(
            selectinload(PatientVaccination.vaccine_scheme),
            selectinload(PatientVaccination.administrator),
        )
        .order_by(PatientVaccination.administered_at.desc())
    )
    vaccinations = result.scalars().all()

    items = []
    for v in vaccinations:
        admin_name = None
        if v.administrator:
            admin_name = f"{v.administrator.first_name} {v.administrator.last_name}"
        items.append(PatientVaccinationResponse(
            id=v.id,
            clinic_id=v.clinic_id,
            patient_id=v.patient_id,
            vaccine_scheme_id=v.vaccine_scheme_id,
            dose_number=v.dose_number,
            administered_at=v.administered_at,
            administered_by=v.administered_by,
            lot_number=v.lot_number,
            next_dose_date=v.next_dose_date,
            inventory_item_id=v.inventory_item_id,
            notes=v.notes,
            created_at=v.created_at,
            vaccine_name=v.vaccine_scheme.name if v.vaccine_scheme else None,
            administrator_name=admin_name,
        ))

    # Calcular dosis pendientes
    pending = await _get_pending_doses(db, clinic_id, patient_id)

    return PatientVaccinationHistory(
        patient_id=patient_id,
        vaccinations=items,
        pending_doses=pending,
    )


async def _get_pending_doses(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID
) -> list[dict]:
    """Calcula dosis pendientes/vencidas para un paciente."""
    # Obtener todas las vacunaciones del paciente
    result = await db.execute(
        select(PatientVaccination)
        .where(
            PatientVaccination.clinic_id == clinic_id,
            PatientVaccination.patient_id == patient_id,
        )
    )
    vaccinations = result.scalars().all()

    # Agrupar por esquema
    by_scheme: dict[str, list] = {}
    for v in vaccinations:
        sid = str(v.vaccine_scheme_id)
        if sid not in by_scheme:
            by_scheme[sid] = []
        by_scheme[sid].append(v)

    pending = []
    today = date.today()

    for sid, doses in by_scheme.items():
        # Obtener esquema
        scheme_result = await db.execute(
            select(VaccineScheme).where(VaccineScheme.id == doses[0].vaccine_scheme_id)
        )
        scheme = scheme_result.scalar_one_or_none()
        if not scheme:
            continue

        applied_numbers = {d.dose_number for d in doses}
        for dose_num in range(1, scheme.doses_total + 1):
            if dose_num not in applied_numbers:
                # Buscar si hay una next_dose_date de la dosis anterior
                prev_dose = next(
                    (d for d in doses if d.dose_number == dose_num - 1), None
                )
                expected_date = prev_dose.next_dose_date if prev_dose else None
                is_overdue = expected_date is not None and expected_date < today

                pending.append({
                    "vaccine_name": scheme.name,
                    "vaccine_scheme_id": str(scheme.id),
                    "dose_number": dose_num,
                    "expected_date": expected_date.isoformat() if expected_date else None,
                    "is_overdue": is_overdue,
                })

    return pending


async def list_overdue_vaccinations(
    db: AsyncSession, clinic_id: UUID
) -> list[dict]:
    """Lista pacientes con vacunas vencidas (next_dose_date < hoy)."""
    today = date.today()
    result = await db.execute(
        select(PatientVaccination)
        .where(
            PatientVaccination.clinic_id == clinic_id,
            PatientVaccination.next_dose_date < today,
        )
        .options(
            selectinload(PatientVaccination.patient),
            selectinload(PatientVaccination.vaccine_scheme),
        )
        .order_by(PatientVaccination.next_dose_date)
    )
    rows = result.scalars().all()

    overdue = []
    for v in rows:
        # Verificar que no se haya aplicado la siguiente dosis
        next_dose_exists = await db.scalar(
            select(func.count()).where(
                PatientVaccination.patient_id == v.patient_id,
                PatientVaccination.vaccine_scheme_id == v.vaccine_scheme_id,
                PatientVaccination.dose_number == v.dose_number + 1,
            )
        )
        if not next_dose_exists:
            patient_name = "Desconocido"
            if v.patient:
                patient_name = f"{v.patient.first_name} {v.patient.last_name}"
            overdue.append({
                "patient_id": str(v.patient_id),
                "patient_name": patient_name,
                "vaccine_name": v.vaccine_scheme.name if v.vaccine_scheme else "N/A",
                "pending_dose": v.dose_number + 1,
                "expected_date": v.next_dose_date.isoformat() if v.next_dose_date else None,
                "days_overdue": (today - v.next_dose_date).days if v.next_dose_date else 0,
            })

    return overdue
