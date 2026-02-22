"""
Schemas Pydantic para el módulo de Servicios.
Catálogo de servicios médicos por clínica.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Create / Update ──────────────────────────────────


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Nombre del servicio")
    description: str | None = None
    duration_minutes: int = Field(30, ge=5, le=480, description="Duración en minutos")
    price: float = Field(0.0, ge=0, description="Precio en PEN")
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", description="Color hex")
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    duration_minutes: int | None = Field(None, ge=5, le=480)
    price: float | None = Field(None, ge=0)
    color: str | None = None
    is_active: bool | None = None


# ── Response ─────────────────────────────────────────


class ServiceResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    description: str | None = None
    duration_minutes: int
    price: float
    color: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServiceListResponse(BaseModel):
    items: list[ServiceResponse]
    total: int
    page: int
    size: int
    pages: int
