"""
Schemas para MedicalRecord — Historia Clínica Electrónica.
Incluye validación de códigos CIE-10.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.medical_record import RecordType


# ── Regex CIE-10 ─────────────────────────────────────
CIE10_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?$")


class MedicalRecordCreate(BaseModel):
    patient_id: UUID
    appointment_id: UUID | None = None
    record_type: RecordType
    cie10_codes: list[str] | None = Field(
        None,
        description="Códigos CIE-10: ['J06.9', 'R50.9']",
    )
    content: dict = Field(
        ...,
        description="Contenido clínico: motivo_consulta, anamnesis, examen_fisico, diagnostico, plan",
    )
    specialty_data: dict | None = Field(
        None,
        description="Datos específicos de especialidad",
    )
    notes: str | None = Field(None, max_length=5000)

    @field_validator("cie10_codes")
    @classmethod
    def validate_cie10(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for code in v:
            if not CIE10_PATTERN.match(code.upper()):
                raise ValueError(
                    f"Código CIE-10 inválido: '{code}'. "
                    "Formato esperado: letra + 2 dígitos + opcional .1-2 dígitos (ej: J06.9)"
                )
        return [c.upper() for c in v]


class MedicalRecordResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID
    appointment_id: UUID | None = None
    record_type: RecordType
    cie10_codes: list[str] | None = None
    content: dict
    specialty_data: dict | None = None
    notes: str | None = None
    signed_at: datetime | None = None
    signed_by: UUID | None = None
    is_signed: bool = False
    doctor_name: str | None = None
    patient_name: str | None = None
    clinic_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MedicalRecordListResponse(BaseModel):
    """Respuesta paginada de historial clínico."""
    items: list[MedicalRecordResponse]
    total: int
    page: int
    size: int
    pages: int


class SignRecordRequest(BaseModel):
    """Confirma la firma digital de un registro clínico."""
    confirm: bool = Field(
        ...,
        description="Debe ser true para confirmar la firma. Una vez firmado, el registro es INMUTABLE.",
    )
