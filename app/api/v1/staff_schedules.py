"""
Endpoints para gestión de turnos de personal.
CRUD de excepciones y vistas consolidadas diaria/semanal/mensual.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.staff_schedule import (
    DailyStaffResponse,
    MonthlyStaffResponse,
    StaffScheduleCreate,
    StaffScheduleOverrideCreate,
    StaffScheduleOverrideResponse,
    StaffScheduleResponse,
    StaffScheduleUpdate,
    WeeklyStaffResponse,
)
from app.services import staff_schedule_service

router = APIRouter()

_ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)
_ALL_STAFF = (
    UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST,
)


# ── StaffSchedule CRUD ──────────────────────────────

@router.post("/schedules", response_model=StaffScheduleResponse, status_code=201)
async def create_staff_schedule(
    data: StaffScheduleCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un turno recurrente para personal no-médico. Solo admin."""
    return await staff_schedule_service.create_staff_schedule(
        db, clinic_id=user.clinic_id, data=data
    )


@router.get("/schedules", response_model=list[StaffScheduleResponse])
async def list_staff_schedules(
    user_id: UUID | None = Query(None),
    user: User = Depends(require_role(*_ALL_STAFF)),
    db: AsyncSession = Depends(get_db),
):
    """Lista turnos recurrentes de personal no-médico."""
    return await staff_schedule_service.list_staff_schedules(
        db, clinic_id=user.clinic_id, user_id=user_id
    )


@router.patch("/schedules/{schedule_id}", response_model=StaffScheduleResponse)
async def update_staff_schedule(
    schedule_id: UUID,
    data: StaffScheduleUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza un turno recurrente. Solo admin."""
    return await staff_schedule_service.update_staff_schedule(
        db, clinic_id=user.clinic_id, schedule_id=schedule_id, data=data
    )


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_staff_schedule(
    schedule_id: UUID,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Elimina (soft) un turno recurrente. Solo admin."""
    await staff_schedule_service.delete_staff_schedule(
        db, clinic_id=user.clinic_id, schedule_id=schedule_id
    )


# ── Overrides CRUD ───────────────────────────────────

@router.post("/overrides", response_model=StaffScheduleOverrideResponse, status_code=201)
async def create_override(
    data: StaffScheduleOverrideCreate,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea una excepción de horario (vacaciones, día libre, cambio de turno, etc.).
    Solo admin de clínica o superior.
    """
    return await staff_schedule_service.create_override(
        db, clinic_id=user.clinic_id, created_by_id=user.id, data=data
    )


@router.get("/overrides", response_model=list[StaffScheduleOverrideResponse])
async def list_overrides(
    date_from: date | None = Query(None, description="Fecha inicio del filtro"),
    date_to: date | None = Query(None, description="Fecha fin del filtro"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista excepciones de horario. Admite filtro por rango de fechas.
    Accesible por admin y doctores.
    """
    return await staff_schedule_service.list_overrides(
        db, clinic_id=user.clinic_id, date_from=date_from, date_to=date_to
    )


@router.delete("/overrides/{override_id}", status_code=204)
async def delete_override(
    override_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
):
    """Elimina una excepción de horario. Solo admin."""
    await staff_schedule_service.delete_override(
        db, clinic_id=user.clinic_id, override_id=override_id
    )


# ── Vistas consolidadas ─────────────────────────────

@router.get("/daily/{target_date}", response_model=DailyStaffResponse)
async def get_daily_staff(
    target_date: date,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
        UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Vista de personal del día: quién trabaja hoy, con qué horario,
    quién tiene día libre, quién es suplente.
    Accesible por todo el personal autenticado.
    """
    return await staff_schedule_service.get_daily_staff(
        db, clinic_id=user.clinic_id, target_date=target_date
    )


@router.get("/weekly/{week_start}", response_model=WeeklyStaffResponse)
async def get_weekly_staff(
    week_start: date,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
        UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Vista de personal semanal. week_start debe ser un lunes.
    Accesible por todo el personal autenticado.
    """
    return await staff_schedule_service.get_weekly_staff(
        db, clinic_id=user.clinic_id, week_start=week_start
    )


@router.get("/monthly/{year}/{month}", response_model=MonthlyStaffResponse)
async def get_monthly_staff(
    year: int,
    month: int,
    target_clinic_id: UUID | None = Query(None, description="Sede a consultar (solo org/super admin)"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN,
        UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Vista tipo ROL-MED del Excel: grilla mensual con todo el personal.
    Accesible por todo el personal autenticado.
    ORG/SUPER admins pueden pasar target_clinic_id para ver otra sede.
    """
    if not (1 <= month <= 12):
        from app.core.exceptions import ValidationException
        raise ValidationException("El mes debe estar entre 1 y 12")

    # Solo org_admin y super_admin pueden ver otras sedes
    can_switch = user.role in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)
    clinic_id = (target_clinic_id if target_clinic_id and can_switch else None) or user.clinic_id

    return await staff_schedule_service.get_monthly_staff(
        db, clinic_id=clinic_id, year=year, month=month
    )
