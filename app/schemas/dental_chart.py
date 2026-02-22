"""
Schemas para DentalChart — Odontograma con sistema FDI.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.dental_chart import ToothCondition, ToothSurface

# Dientes válidos FDI: adultos (11-18, 21-28, 31-38, 41-48)
# y deciduos (51-55, 61-65, 71-75, 81-85)
VALID_ADULT_TEETH = set(
    list(range(11, 19)) + list(range(21, 29)) +
    list(range(31, 39)) + list(range(41, 49))
)
VALID_DECIDUOUS_TEETH = set(
    list(range(51, 56)) + list(range(61, 66)) +
    list(range(71, 76)) + list(range(81, 86))
)
VALID_TEETH = VALID_ADULT_TEETH | VALID_DECIDUOUS_TEETH


class DentalChartCreate(BaseModel):
    patient_id: UUID
    record_id: UUID | None = None
    tooth_number: int = Field(..., description="Número FDI del diente")
    surfaces: list[str] | None = Field(
        None, description="Superficies afectadas: ['V','O','M','D','L']"
    )
    condition: ToothCondition
    treatment: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)

    @field_validator("tooth_number")
    @classmethod
    def validate_tooth(cls, v: int) -> int:
        if v not in VALID_TEETH:
            raise ValueError(
                f"Número de diente FDI inválido: {v}. "
                "Adultos: 11-18, 21-28, 31-38, 41-48. "
                "Deciduos: 51-55, 61-65, 71-75, 81-85."
            )
        return v

    @field_validator("surfaces")
    @classmethod
    def validate_surfaces(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        valid = {s.value for s in ToothSurface}
        for s in v:
            if s.upper() not in valid:
                raise ValueError(
                    f"Superficie inválida: '{s}'. Válidas: {', '.join(valid)}"
                )
        return [s.upper() for s in v]


class DentalChartResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    record_id: UUID | None = None
    doctor_id: UUID
    tooth_number: int
    surfaces: list[str] | None = None
    condition: ToothCondition
    treatment: str | None = None
    notes: str | None = None
    doctor_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ToothStatus(BaseModel):
    """Estado actual de un diente (último registro)."""
    tooth_number: int
    condition: ToothCondition
    surfaces: list[str] | None = None
    treatment: str | None = None
    last_updated: datetime
    history_count: int = 0


class FullDentalChartResponse(BaseModel):
    """Odontograma completo del paciente — estado actual de todos los dientes."""
    patient_id: UUID
    teeth: list[ToothStatus]
    total_entries: int
