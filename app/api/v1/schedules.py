"""
Endpoints para gestión de horarios de doctores.
Solo clinic_admin y super_admin pueden gestionar horarios.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.appointment import (
    DoctorScheduleCreate,
    DoctorScheduleResponse,
    DoctorScheduleUpdate,
)
from app.services import appointment_service

router = APIRouter()

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _schedule_to_response(schedule) -> DoctorScheduleResponse:
    """Convierte un modelo DoctorSchedule a su schema de respuesta."""
    return DoctorScheduleResponse(
        id=schedule.id,
        clinic_id=schedule.clinic_id,
        doctor_id=schedule.doctor_id,
        day_of_week=schedule.day_of_week,
        day_name=DAY_NAMES[schedule.day_of_week] if 0 <= schedule.day_of_week <= 6 else None,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        slot_duration_minutes=schedule.slot_duration_minutes,
        is_active=schedule.is_active,
    )


@router.get("/{doctor_id}", response_model=list[DoctorScheduleResponse])
async def get_doctor_schedules(
    doctor_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Obtiene todos los horarios activos de un doctor.
    Doctores solo pueden ver sus propios horarios.
    """
    # Un doctor/obstetra solo puede ver sus propios horarios
    if user.role in (UserRole.DOCTOR, UserRole.OBSTETRA) and user.id != doctor_id:
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("Solo puede ver sus propios horarios")

    schedules = await appointment_service.get_doctor_schedules(
        db, clinic_id=user.clinic_id, doctor_id=doctor_id
    )
    return [_schedule_to_response(s) for s in schedules]


@router.post("", response_model=DoctorScheduleResponse, status_code=201)
async def create_schedule(
    data: DoctorScheduleCreate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un bloque de horario para un doctor.
    Solo admin de clínica o super admin.
    """
    schedule = await appointment_service.create_schedule(
        db,
        clinic_id=user.clinic_id,
        doctor_id=data.doctor_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        slot_duration_minutes=data.slot_duration_minutes,
    )
    return _schedule_to_response(schedule)


@router.put("/{schedule_id}", response_model=DoctorScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    data: DoctorScheduleUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un bloque de horario existente."""
    schedule = await appointment_service.update_schedule(
        db,
        schedule_id=schedule_id,
        clinic_id=user.clinic_id,
        start_time=data.start_time,
        end_time=data.end_time,
        slot_duration_minutes=data.slot_duration_minutes,
        is_active=data.is_active,
    )
    return _schedule_to_response(schedule)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: UUID,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Desactiva un bloque de horario (soft delete)."""
    await appointment_service.delete_schedule(
        db, schedule_id=schedule_id, clinic_id=user.clinic_id
    )
