"""
Servicio de turnos de personal: CRUD de overrides y vistas
consolidadas diaria/semanal/mensual.
"""

import calendar
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundException, ValidationException
from app.models.doctor_schedule import DoctorSchedule
from app.models.staff_schedule_override import StaffScheduleOverride, OverrideType
from app.models.user import User, UserRole
from app.schemas.staff_schedule import (
    DailyStaffResponse,
    MonthlyStaffResponse,
    StaffMember,
    StaffScheduleOverrideCreate,
    StaffScheduleOverrideResponse,
    UserEmbed,
    WeeklyStaffResponse,
)


# ── Helpers ──────────────────────────────────────────

def _user_to_embed(user: User) -> UserEmbed:
    """Convierte un User a un embed mínimo."""
    return UserEmbed(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        specialty=user.specialty,
        specialty_type=user.specialty_type,
        position=user.position,
    )


def _override_to_response(override: StaffScheduleOverride) -> StaffScheduleOverrideResponse:
    """Convierte un StaffScheduleOverride a su schema de respuesta."""
    return StaffScheduleOverrideResponse(
        id=override.id,
        clinic_id=override.clinic_id,
        user=_user_to_embed(override.user),
        override_type=override.override_type,
        date_start=override.date_start,
        date_end=override.date_end,
        new_start_time=override.new_start_time,
        new_end_time=override.new_end_time,
        substitute=_user_to_embed(override.substitute) if override.substitute else None,
        reason=override.reason,
        created_by=_user_to_embed(override.creator),
        created_at=override.created_at,
    )


def _load_override_options():
    """Opciones de carga eager para StaffScheduleOverride."""
    return [
        joinedload(StaffScheduleOverride.user),
        joinedload(StaffScheduleOverride.substitute),
        joinedload(StaffScheduleOverride.creator),
    ]


# ── CRUD de Overrides ────────────────────────────────

async def create_override(
    db: AsyncSession,
    clinic_id: UUID,
    created_by_id: UUID,
    data: StaffScheduleOverrideCreate,
) -> StaffScheduleOverrideResponse:
    """Crea una excepción de horario validando que el usuario existe."""
    # Verificar que el usuario afectado existe y pertenece a la clínica
    user_result = await db.execute(
        select(User).where(
            User.id == data.user_id,
            User.clinic_id == clinic_id,
            User.is_active.is_(True),
        )
    )
    if not user_result.scalar_one_or_none():
        raise NotFoundException("Usuario")

    # Si hay suplente, verificar que existe
    if data.substitute_user_id:
        sub_result = await db.execute(
            select(User).where(
                User.id == data.substitute_user_id,
                User.clinic_id == clinic_id,
                User.is_active.is_(True),
            )
        )
        if not sub_result.scalar_one_or_none():
            raise NotFoundException("Usuario suplente")

    # Validar que shift_change/extra_shift tienen horarios
    if data.override_type in (OverrideType.SHIFT_CHANGE, OverrideType.EXTRA_SHIFT):
        if not data.new_start_time or not data.new_end_time:
            raise ValidationException(
                "Los cambios de turno y turnos extra requieren new_start_time y new_end_time"
            )

    override = StaffScheduleOverride(
        clinic_id=clinic_id,
        user_id=data.user_id,
        override_type=data.override_type,
        date_start=data.date_start,
        date_end=data.date_end,
        new_start_time=data.new_start_time,
        new_end_time=data.new_end_time,
        substitute_user_id=data.substitute_user_id,
        reason=data.reason,
        created_by=created_by_id,
    )
    db.add(override)
    await db.flush()

    # Recargar con relaciones
    result = await db.execute(
        select(StaffScheduleOverride)
        .options(*_load_override_options())
        .where(StaffScheduleOverride.id == override.id)
    )
    override = result.scalar_one()

    return _override_to_response(override)


async def list_overrides(
    db: AsyncSession,
    clinic_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[StaffScheduleOverrideResponse]:
    """Lista excepciones de horario en un rango de fechas."""
    query = (
        select(StaffScheduleOverride)
        .options(*_load_override_options())
        .where(StaffScheduleOverride.clinic_id == clinic_id)
    )

    if date_from:
        query = query.where(StaffScheduleOverride.date_end >= date_from)
    if date_to:
        query = query.where(StaffScheduleOverride.date_start <= date_to)

    query = query.order_by(StaffScheduleOverride.date_start)

    result = await db.execute(query)
    overrides = result.scalars().unique().all()

    return [_override_to_response(o) for o in overrides]


async def delete_override(
    db: AsyncSession,
    clinic_id: UUID,
    override_id: UUID,
) -> None:
    """Elimina una excepción de horario."""
    result = await db.execute(
        select(StaffScheduleOverride).where(
            StaffScheduleOverride.id == override_id,
            StaffScheduleOverride.clinic_id == clinic_id,
        )
    )
    override = result.scalar_one_or_none()
    if not override:
        raise NotFoundException("Excepción de horario")

    await db.delete(override)
    await db.flush()


# ── Vistas consolidadas ─────────────────────────────

async def get_daily_staff(
    db: AsyncSession,
    clinic_id: UUID,
    target_date: date,
) -> DailyStaffResponse:
    """
    Construye la vista de personal para un día.

    1. Obtiene todos los usuarios activos de la clínica con horario
       configurado para ese día de la semana.
    2. Aplica overrides activos para la fecha.
    3. Retorna lista con horarios efectivos.
    """
    day_of_week = target_date.weekday()  # 0=Lunes ... 6=Domingo

    # Obtener todos los horarios activos para este día de la semana
    schedules_result = await db.execute(
        select(DoctorSchedule)
        .options(joinedload(DoctorSchedule.doctor))
        .where(
            DoctorSchedule.clinic_id == clinic_id,
            DoctorSchedule.day_of_week == day_of_week,
            DoctorSchedule.is_active.is_(True),
        )
    )
    schedules = schedules_result.scalars().unique().all()

    # Obtener overrides activos para esta fecha
    overrides_result = await db.execute(
        select(StaffScheduleOverride)
        .options(
            joinedload(StaffScheduleOverride.user),
            joinedload(StaffScheduleOverride.substitute),
        )
        .where(
            StaffScheduleOverride.clinic_id == clinic_id,
            StaffScheduleOverride.date_start <= target_date,
            StaffScheduleOverride.date_end >= target_date,
        )
    )
    overrides = overrides_result.scalars().unique().all()

    # Indexar overrides por user_id
    overrides_by_user: dict[UUID, StaffScheduleOverride] = {}
    for ovr in overrides:
        overrides_by_user[ovr.user_id] = ovr

    staff_members: list[StaffMember] = []
    seen_user_ids: set[UUID] = set()

    # Procesar personal con horario regular
    for sched in schedules:
        doctor = sched.doctor
        if not doctor or not doctor.is_active:
            continue

        user_id = doctor.id
        seen_user_ids.add(user_id)

        ovr = overrides_by_user.get(user_id)

        if ovr:
            # Hay un override para este usuario hoy
            if ovr.override_type in (OverrideType.DAY_OFF, OverrideType.VACATION, OverrideType.HOLIDAY):
                # No trabaja hoy
                staff_members.append(StaffMember(
                    user_id=user_id,
                    first_name=doctor.first_name,
                    last_name=doctor.last_name,
                    role=doctor.role.value,
                    specialty=doctor.specialty,
                    specialty_type=doctor.specialty_type,
                    position=doctor.position,
                    schedule_start=None,
                    schedule_end=None,
                    is_override=True,
                    override_type=ovr.override_type,
                    substitute_name=(
                        f"{ovr.substitute.first_name} {ovr.substitute.last_name}"
                        if ovr.substitute else None
                    ),
                    is_working=False,
                ))
            elif ovr.override_type == OverrideType.SHIFT_CHANGE:
                # Trabaja con horario diferente
                staff_members.append(StaffMember(
                    user_id=user_id,
                    first_name=doctor.first_name,
                    last_name=doctor.last_name,
                    role=doctor.role.value,
                    specialty=doctor.specialty,
                    specialty_type=doctor.specialty_type,
                    position=doctor.position,
                    schedule_start=ovr.new_start_time,
                    schedule_end=ovr.new_end_time,
                    is_override=True,
                    override_type=ovr.override_type,
                    is_working=True,
                ))
            else:
                # extra_shift u otro: mantener horario normal + override info
                staff_members.append(StaffMember(
                    user_id=user_id,
                    first_name=doctor.first_name,
                    last_name=doctor.last_name,
                    role=doctor.role.value,
                    specialty=doctor.specialty,
                    specialty_type=doctor.specialty_type,
                    position=doctor.position,
                    schedule_start=sched.start_time,
                    schedule_end=sched.end_time,
                    is_override=True,
                    override_type=ovr.override_type,
                    is_working=True,
                ))
        else:
            # Sin override: horario normal
            staff_members.append(StaffMember(
                user_id=user_id,
                first_name=doctor.first_name,
                last_name=doctor.last_name,
                role=doctor.role.value,
                specialty=doctor.specialty,
                specialty_type=doctor.specialty_type,
                position=doctor.position,
                schedule_start=sched.start_time,
                schedule_end=sched.end_time,
                is_override=False,
                is_working=True,
            ))

    # Procesar cualquier override para personas SIN horario regular mapeado
    for ovr in overrides:
        if ovr.user_id in seen_user_ids:
            continue
        
        user = ovr.user
        if not user or not user.is_active:
            continue
            
        # Determinar si trabaja o no basado en el tipo de override
        is_working = ovr.override_type in (OverrideType.EXTRA_SHIFT, OverrideType.SHIFT_CHANGE)
        
        staff_members.append(StaffMember(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            specialty=user.specialty,
            specialty_type=user.specialty_type,
            position=user.position,
            schedule_start=ovr.new_start_time if is_working else None,
            schedule_end=ovr.new_end_time if is_working else None,
            is_override=True,
            override_type=ovr.override_type,
            substitute_name=(
                f"{ovr.substitute.first_name} {ovr.substitute.last_name}"
                if ovr.substitute else None
            ),
            is_working=is_working,
        ))

    return DailyStaffResponse(date=target_date, staff=staff_members)


async def get_weekly_staff(
    db: AsyncSession,
    clinic_id: UUID,
    week_start: date,
) -> WeeklyStaffResponse:
    """Construye la vista de personal para una semana (7 días)."""
    days: list[DailyStaffResponse] = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        daily = await get_daily_staff(db, clinic_id, day)
        days.append(daily)

    return WeeklyStaffResponse(week_start=week_start, days=days)


async def get_monthly_staff(
    db: AsyncSession,
    clinic_id: UUID,
    year: int,
    month: int,
) -> MonthlyStaffResponse:
    """Construye la vista de personal para un mes completo."""
    _, days_in_month = calendar.monthrange(year, month)
    days: list[DailyStaffResponse] = []
    for day_num in range(1, days_in_month + 1):
        target = date(year, month, day_num)
        daily = await get_daily_staff(db, clinic_id, target)
        days.append(daily)

    return MonthlyStaffResponse(year=year, month=month, days=days)
