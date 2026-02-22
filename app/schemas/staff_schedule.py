"""
Schemas para gestión de turnos de personal — overrides y vistas consolidadas.
"""

from datetime import date, time, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.staff_schedule_override import OverrideType


# ── Override CRUD ────────────────────────────────────

class StaffScheduleOverrideCreate(BaseModel):
    """Input para crear una excepción de horario."""
    user_id: UUID
    override_type: OverrideType
    date_start: date
    date_end: date
    new_start_time: time | None = None
    new_end_time: time | None = None
    substitute_user_id: UUID | None = None
    reason: str | None = Field(None, max_length=500)

    @field_validator("date_end")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("date_start")
        if start and v < start:
            raise ValueError("date_end debe ser igual o posterior a date_start")
        return v

    @field_validator("new_end_time")
    @classmethod
    def time_end_after_start(cls, v: time | None, info) -> time | None:
        if v is None:
            return v
        start = info.data.get("new_start_time")
        if start and v <= start:
            raise ValueError("new_end_time debe ser posterior a new_start_time")
        return v


class UserEmbed(BaseModel):
    """Datos mínimos de un usuario embebidos en respuestas."""
    id: UUID
    first_name: str
    last_name: str
    role: str
    specialty: str | None = None
    specialty_type: str | None = None
    position: str | None = None

    model_config = {"from_attributes": True}


class StaffScheduleOverrideResponse(BaseModel):
    """Respuesta de una excepción de horario."""
    id: UUID
    clinic_id: UUID
    user: UserEmbed
    override_type: OverrideType
    date_start: date
    date_end: date
    new_start_time: time | None = None
    new_end_time: time | None = None
    substitute: UserEmbed | None = None
    reason: str | None = None
    created_by: UserEmbed
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Vistas consolidadas del staff ────────────────────

class StaffMember(BaseModel):
    """Un miembro del staff con su horario efectivo para un día."""
    user_id: UUID
    first_name: str
    last_name: str
    role: str
    specialty: str | None = None
    specialty_type: str | None = None
    position: str | None = None
    schedule_start: time | None = None
    schedule_end: time | None = None
    is_override: bool = False
    override_type: OverrideType | None = None
    substitute_name: str | None = None
    is_working: bool = True


class DailyStaffResponse(BaseModel):
    """Staff efectivo de un día."""
    date: date
    staff: list[StaffMember]


class WeeklyStaffResponse(BaseModel):
    """Staff efectivo de una semana (7 días)."""
    week_start: date
    days: list[DailyStaffResponse]


class MonthlyStaffResponse(BaseModel):
    """Staff efectivo de un mes completo."""
    year: int
    month: int
    days: list[DailyStaffResponse]
