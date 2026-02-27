"""
Schemas Pydantic para el módulo de Servicios.
Catálogo de servicios médicos por clínica.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.service import ServiceCategory


# ── Create / Update ──────────────────────────────────


class ServiceCreate(BaseModel):
    code: str | None = Field(None, max_length=20, description="Código interno")
    name: str = Field(..., min_length=1, max_length=150, description="Nombre del servicio")
    description: str | None = None
    category: ServiceCategory = Field(ServiceCategory.OTHER, description="Categoría del servicio")
    duration_minutes: int = Field(30, ge=5, le=480, description="Duración en minutos")
    price: float = Field(0.0, ge=0, description="Precio de venta en PEN")
    cost_price: float = Field(0.0, ge=0, description="Precio de costo en PEN")
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", description="Color hex")
    is_active: bool = True


class ServiceUpdate(BaseModel):
    code: str | None = None
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    category: ServiceCategory | None = None
    duration_minutes: int | None = Field(None, ge=5, le=480)
    price: float | None = Field(None, ge=0)
    cost_price: float | None = Field(None, ge=0)
    color: str | None = None
    is_active: bool | None = None


# ── Response ─────────────────────────────────────────


class ServiceResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    code: str | None = None
    name: str
    description: str | None = None
    category: ServiceCategory
    duration_minutes: int
    price: float
    cost_price: float
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
