"""
Schemas para OphthalmicExam — Examen oftalmológico.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.ophthalmic_exam import EyeSide


class OphthalmicExamCreate(BaseModel):
    patient_id: UUID
    record_id: UUID | None = None
    eye: EyeSide
    visual_acuity_uncorrected: str | None = Field(None, max_length=20)
    visual_acuity_corrected: str | None = Field(None, max_length=20)
    sphere: float | None = Field(None, ge=-20.0, le=20.0, description="Esfera (dioptrías)")
    cylinder: float | None = Field(None, ge=-10.0, le=10.0, description="Cilindro (dioptrías)")
    axis: int | None = Field(None, ge=0, le=180, description="Eje (grados)")
    addition: float | None = Field(None, ge=0.0, le=4.0, description="Adición presbicia")
    iop: float | None = Field(None, ge=0, le=80, description="PIO (mmHg)")
    extra_data: dict | None = Field(None, description="Fondo de ojo, biomicroscopía, etc.")
    notes: str | None = Field(None, max_length=5000)

    @field_validator("axis")
    @classmethod
    def axis_requires_cylinder(cls, v: int | None, info) -> int | None:
        if v is not None and info.data.get("cylinder") is None:
            raise ValueError("El eje solo se indica cuando hay cilindro")
        return v


class OphthalmicExamResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    record_id: UUID | None = None
    doctor_id: UUID
    eye: EyeSide
    visual_acuity_uncorrected: str | None = None
    visual_acuity_corrected: str | None = None
    sphere: float | None = None
    cylinder: float | None = None
    axis: int | None = None
    addition: float | None = None
    iop: float | None = None
    extra_data: dict | None = None
    notes: str | None = None
    doctor_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OphthalmicHistoryResponse(BaseModel):
    """Historial oftalmológico completo de un paciente."""
    patient_id: UUID
    exams: list[OphthalmicExamResponse]
    total_exams: int
