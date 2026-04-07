"""Schemas para ImagingTemplate — plantillas guardables de informes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.imaging_report import ImagingStudyType


class ImagingTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    study_type: ImagingStudyType
    findings: dict[str, Any] = Field(default_factory=dict)
    conclusion_items: list[str] = Field(default_factory=list)
    recommendations: str | None = Field(None, max_length=5000)


class ImagingTemplateResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    created_by: UUID
    name: str
    study_type: ImagingStudyType
    findings: dict[str, Any]
    conclusion_items: list[str]
    recommendations: str | None = None
    created_at: datetime
    creator_name: str | None = None

    model_config = {"from_attributes": True}


class ImagingTemplateListResponse(BaseModel):
    items: list[ImagingTemplateResponse]
    total: int
