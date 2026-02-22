"""
Schemas para PrenatalVisit — Control prenatal CLAP/SIP.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PrenatalVisitCreate(BaseModel):
    patient_id: UUID
    record_id: UUID | None = None
    gestational_week: int = Field(..., ge=1, le=45, description="Semana de gestación")
    weight: float | None = Field(None, gt=0, le=300, description="Peso en kg")
    blood_pressure_systolic: int | None = Field(None, ge=50, le=300, description="PA sistólica (mmHg)")
    blood_pressure_diastolic: int | None = Field(None, ge=30, le=200, description="PA diastólica (mmHg)")
    uterine_height: float | None = Field(None, ge=0, le=50, description="Altura uterina (cm)")
    fetal_heart_rate: int | None = Field(None, ge=60, le=220, description="FCF (lpm)")
    presentation: str | None = Field(None, max_length=50)
    fetal_movements: str | None = Field(None, max_length=50)
    edema: str | None = Field(None, max_length=50)
    labs: dict | None = Field(None, description="Laboratorios: hemoglobina, glucosa, orina, etc.")
    notes: str | None = Field(None, max_length=5000)
    next_appointment_notes: str | None = Field(None, max_length=500)

    @field_validator("blood_pressure_diastolic")
    @classmethod
    def diastolic_less_than_systolic(cls, v: int | None, info) -> int | None:
        if v is None:
            return v
        systolic = info.data.get("blood_pressure_systolic")
        if systolic and v >= systolic:
            raise ValueError("PA diastólica debe ser menor que la sistólica")
        return v


class PrenatalVisitResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    record_id: UUID | None = None
    doctor_id: UUID
    gestational_week: int
    weight: float | None = None
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    blood_pressure: str | None = None
    uterine_height: float | None = None
    fetal_heart_rate: int | None = None
    presentation: str | None = None
    fetal_movements: str | None = None
    edema: str | None = None
    labs: dict | None = None
    notes: str | None = None
    next_appointment_notes: str | None = None
    doctor_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PrenatalHistoryResponse(BaseModel):
    """Historial prenatal completo de una paciente."""
    patient_id: UUID
    visits: list[PrenatalVisitResponse]
    total_visits: int
