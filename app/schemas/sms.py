"""
Schemas para SMS — Configuración, historial de mensajes y test.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Configuración SMS ─────────────────────────────────

class SmsConfigResponse(BaseModel):
    """Configuración de SMS de la clínica."""
    enabled: bool = False
    reminder_hours_before: int = Field(24, ge=1, le=72)
    reminder_frequency: str = Field("once", description="once | twice")
    second_reminder_hours: int | None = Field(None, ge=1, le=24)
    send_time_start: str = Field("08:00", description="Hora inicio ventana envío HH:MM")
    send_time_end: str = Field("20:00", description="Hora fin ventana envío HH:MM")
    template_confirmation: str = Field(
        "Hola {patient_name}, su cita con {doctor_name} ha sido confirmada "
        "para el {date} a las {time} en {clinic_name}. ¡Lo esperamos!",
        max_length=1000,
    )
    template_reminder: str = Field(
        "Recordatorio: {patient_name}, tiene cita con {doctor_name} "
        "el {date} a las {time} en {clinic_name}. "
        "Confirme respondiendo SI o cancele con CANCELAR.",
        max_length=1000,
    )
    template_followup: str = Field(
        "Hola {patient_name}, esperamos que su visita a {clinic_name} "
        "haya sido satisfactoria. ¡Gracias por su confianza!",
        max_length=1000,
    )


class SmsConfigUpdate(BaseModel):
    """Actualización de configuración SMS."""
    enabled: bool | None = None
    reminder_hours_before: int | None = Field(None, ge=1, le=72)
    reminder_frequency: str | None = Field(None, description="once | twice")
    second_reminder_hours: int | None = Field(None, ge=1, le=24)
    send_time_start: str | None = None
    send_time_end: str | None = None
    template_confirmation: str | None = Field(None, max_length=1000)
    template_reminder: str | None = Field(None, max_length=1000)
    template_followup: str | None = Field(None, max_length=1000)


# ── Historial de mensajes ─────────────────────────────

class SmsPatientEmbed(BaseModel):
    """Datos mínimos del paciente en el historial SMS."""
    first_name: str
    last_name: str


class SmsMessageResponse(BaseModel):
    """Un mensaje SMS del historial."""
    id: UUID
    patient_id: UUID | None = None
    phone: str
    message: str
    sms_type: str
    status: str
    sent_at: datetime
    error_message: str | None = None
    patient: SmsPatientEmbed | None = None

    model_config = {"from_attributes": True}


class SmsMessageListResponse(BaseModel):
    """Respuesta paginada del historial de mensajes."""
    items: list[SmsMessageResponse]
    total: int
    page: int
    page_size: int


# ── Test SMS ──────────────────────────────────────────

class SmsTestRequest(BaseModel):
    """Request para enviar un SMS de prueba."""
    phone: str = Field(..., min_length=8, max_length=20, description="Número con código de país (+51...)")


class SmsTestResponse(BaseModel):
    """Respuesta del envío de SMS de prueba."""
    success: bool
    message: str
    twilio_sid: str | None = None
