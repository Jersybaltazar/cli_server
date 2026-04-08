"""
Schemas Pydantic para Prescription / PrescriptionItem.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Items ─────────────────────────────────────────────

class PrescriptionItemBase(BaseModel):
    medication_id: UUID | None = None
    medication: str = Field(..., min_length=1, max_length=255)
    presentation: str | None = Field(None, max_length=120)
    dose: str | None = Field(None, max_length=120)
    frequency: str | None = Field(None, max_length=120)
    duration: str | None = Field(None, max_length=120)
    quantity: str | None = Field(None, max_length=60)
    instructions: str | None = Field(None, max_length=2000)


class PrescriptionItemCreate(PrescriptionItemBase):
    pass


class PrescriptionItemResponse(PrescriptionItemBase):
    id: UUID
    position: int

    model_config = {"from_attributes": True}


# ── Receta ────────────────────────────────────────────

class PrescriptionCreate(BaseModel):
    patient_id: UUID
    record_id: UUID | None = None
    diagnosis: str | None = Field(None, max_length=2000)
    cie10_code: str | None = Field(None, max_length=10)
    notes: str | None = Field(None, max_length=4000)
    items: list[PrescriptionItemCreate] = Field(default_factory=list)


class PrescriptionUpdate(BaseModel):
    diagnosis: str | None = Field(None, max_length=2000)
    cie10_code: str | None = Field(None, max_length=10)
    notes: str | None = Field(None, max_length=4000)
    items: list[PrescriptionItemCreate] | None = None


class PrescriptionResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID
    record_id: UUID | None = None
    diagnosis: str | None = None
    cie10_code: str | None = None
    notes: str | None = None
    serial_number: str | None = None
    items: list[PrescriptionItemResponse]
    created_at: datetime
    updated_at: datetime

    signed_at: datetime | None = None
    signed_by: UUID | None = None
    is_signed: bool = False

    # Datos derivados para encabezado
    patient_name: str | None = None
    patient_age: int | None = None
    patient_document: str | None = None
    doctor_name: str | None = None
    signer_name: str | None = None

    model_config = {"from_attributes": True}


class PrescriptionListResponse(BaseModel):
    items: list[PrescriptionResponse]
    total: int


# ── Plantillas reutilizables ──────────────────────────

class PrescriptionTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    diagnosis: str | None = Field(None, max_length=2000)
    cie10_code: str | None = Field(None, max_length=10)
    notes: str | None = Field(None, max_length=4000)
    items: list[PrescriptionItemCreate] = Field(default_factory=list)


class PrescriptionTemplateResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    created_by: UUID
    name: str
    diagnosis: str | None = None
    cie10_code: str | None = None
    notes: str | None = None
    items: list[dict]
    created_at: datetime
    creator_name: str | None = None

    model_config = {"from_attributes": True}


class PrescriptionTemplateListResponse(BaseModel):
    items: list[PrescriptionTemplateResponse]
    total: int
