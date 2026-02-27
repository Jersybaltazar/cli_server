"""
Schemas para Vacunación — Esquemas de vacunas y registro de dosis.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── VaccineScheme ──────────────────────────────────────

class VaccineSchemeCreate(BaseModel):
    name: str = Field(..., max_length=200)
    doses_total: int = Field(..., ge=1, le=10)
    dose_intervals_months: list[int] = Field(
        ..., description="Intervalos en meses [0, 2, 6]"
    )
    notes: str | None = None


class VaccineSchemeUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    doses_total: int | None = Field(None, ge=1, le=10)
    dose_intervals_months: list[int] | None = None
    notes: str | None = None
    is_active: bool | None = None


class VaccineSchemeResponse(BaseModel):
    id: UUID
    name: str
    doses_total: int
    dose_intervals_months: list[int]
    notes: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── PatientVaccination ─────────────────────────────────

class PatientVaccinationCreate(BaseModel):
    patient_id: UUID
    vaccine_scheme_id: UUID
    dose_number: int = Field(..., ge=1)
    lot_number: str | None = Field(None, max_length=50)
    inventory_item_id: UUID | None = None
    notes: str | None = None


class PatientVaccinationResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    vaccine_scheme_id: UUID
    dose_number: int
    administered_at: datetime
    administered_by: UUID
    lot_number: str | None = None
    next_dose_date: date | None = None
    inventory_item_id: UUID | None = None
    notes: str | None = None
    created_at: datetime

    # Enriquecidos
    vaccine_name: str | None = None
    administrator_name: str | None = None

    model_config = {"from_attributes": True}


class PatientVaccinationHistory(BaseModel):
    """Historial de vacunación de un paciente."""
    patient_id: UUID
    vaccinations: list[PatientVaccinationResponse]
    pending_doses: list[dict] = Field(
        default=[], description="Dosis pendientes por esquema"
    )
