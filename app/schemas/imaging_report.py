"""
Schemas para ImagingReport — Informes ecográficos y procedimientos.

En la Fase 0 se acepta `findings` como dict genérico. En fases posteriores
se agregará validación por discriminador según study_type.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.imaging_report import ImagingStudyType


class ImagingReportCreate(BaseModel):
    patient_id: UUID
    study_type: ImagingStudyType
    record_id: UUID | None = None
    findings: dict[str, Any] = Field(default_factory=dict)
    conclusion_items: list[str] = Field(default_factory=list)
    recommendations: str | None = Field(None, max_length=5000)


class ImagingReportUpdate(BaseModel):
    findings: dict[str, Any] | None = None
    conclusion_items: list[str] | None = None
    recommendations: str | None = Field(None, max_length=5000)


class ImagingReportResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID
    record_id: UUID | None = None
    study_type: ImagingStudyType
    findings: dict[str, Any]
    conclusion_items: list[str]
    recommendations: str | None = None
    created_at: datetime
    updated_at: datetime

    # Firma digital
    signed_at: datetime | None = None
    signed_by: UUID | None = None
    is_signed: bool = False

    # Datos derivados para el encabezado del informe
    patient_name: str | None = None
    patient_age: int | None = None
    patient_document: str | None = None
    doctor_name: str | None = None
    signer_name: str | None = None

    model_config = {"from_attributes": True}


class ImagingReportListResponse(BaseModel):
    """Lista paginada simple para la Fase 0."""
    items: list[ImagingReportResponse]
    total: int
