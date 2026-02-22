"""
Schemas para Appointment — citas médicas.
Incluye schemas para disponibilidad y reserva pública.
"""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.appointment import AppointmentStatus


# ── CRUD de Citas ────────────────────────────────────

class AppointmentCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    start_time: datetime
    end_time: datetime
    service_type: str = Field(..., min_length=2, max_length=100)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time debe ser posterior a start_time")
        return v


class AppointmentUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    service_type: str | None = Field(None, min_length=2, max_length=100)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: datetime | None, info) -> datetime | None:
        if v is None:
            return v
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time debe ser posterior a start_time")
        return v


class AppointmentStatusChange(BaseModel):
    """Schema para cambiar el estado de una cita."""
    status: AppointmentStatus
    cancellation_reason: str | None = Field(None, max_length=500)


class AppointmentPatientEmbed(BaseModel):
    """Datos del paciente embebidos en la respuesta de cita."""
    id: UUID
    dni: str
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None


class AppointmentDoctorEmbed(BaseModel):
    """Datos del doctor embebidos en la respuesta de cita."""
    id: UUID
    first_name: str
    last_name: str
    specialty: str | None = None
    cmp_number: str | None = None


class AppointmentResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    service_type: str
    notes: str | None = None
    cancellation_reason: str | None = None
    cancelled_by: UUID | None = None

    # Datos de relaciones
    patient_name: str | None = None
    doctor_name: str | None = None
    clinic_name: str | None = None
    patient: AppointmentPatientEmbed | None = None
    doctor: AppointmentDoctorEmbed | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AppointmentListResponse(BaseModel):
    """Respuesta paginada de listado de citas."""
    items: list[AppointmentResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Horarios de Doctor ───────────────────────────────

class DoctorScheduleCreate(BaseModel):
    doctor_id: UUID
    day_of_week: int = Field(..., ge=0, le=6, description="0=Lunes ... 6=Domingo")
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(30, ge=10, le=120)

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time debe ser posterior a start_time")
        return v


class DoctorScheduleUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    slot_duration_minutes: int | None = Field(None, ge=10, le=120)
    is_active: bool | None = None


class DoctorScheduleResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    day_of_week: int
    day_name: str | None = None
    start_time: time
    end_time: time
    slot_duration_minutes: int
    is_active: bool

    model_config = {"from_attributes": True}


# ── Disponibilidad / Slots ───────────────────────────

class TimeSlot(BaseModel):
    """Un slot de tiempo disponible para agendar."""
    start_time: datetime
    end_time: datetime
    available: bool = True


class AvailabilityRequest(BaseModel):
    """Parámetros para consultar disponibilidad."""
    doctor_id: UUID
    date: date


class AvailabilityResponse(BaseModel):
    """Respuesta con slots disponibles para un doctor en una fecha."""
    doctor_id: UUID
    doctor_name: str | None = None
    date: date
    slots: list[TimeSlot]


# ── Reserva Pública Online ───────────────────────────

class PublicBookingRequest(BaseModel):
    """Schema para reserva desde el link público (sin autenticación)."""
    # Datos de la cita
    doctor_id: UUID
    start_time: datetime
    end_time: datetime
    service_type: str = Field(..., min_length=2, max_length=100)
    notes: str | None = Field(None, max_length=2000)

    # Datos del paciente (nuevo o existente)
    patient_dni: str = Field(..., min_length=8, max_length=15)
    patient_first_name: str = Field(..., min_length=2, max_length=100)
    patient_last_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: str | None = Field(None, max_length=20)
    patient_email: str | None = Field(None, max_length=255)


class PublicBookingResponse(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    status: AppointmentStatus
    start_time: datetime
    end_time: datetime
    doctor_name: str | None = None
    message: str = "Cita reservada exitosamente"
