"""Schemas Pydantic v2 para ServicePackage y PackageItem."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── PackageItem ──────────────────────────


class PackageItemCreate(BaseModel):
    service_id: UUID
    quantity: int = Field(1, ge=1)
    description_override: str | None = None
    gestational_week_target: int | None = Field(
        None, ge=1, le=42,
        description="Semana gestacional objetivo para auto-agendar"
    )


class PackageItemUpdate(BaseModel):
    service_id: UUID | None = None
    quantity: int | None = Field(None, ge=1)
    description_override: str | None = None
    gestational_week_target: int | None = None


class PackageItemResponse(BaseModel):
    id: UUID
    package_id: UUID
    service_id: UUID
    quantity: int
    description_override: str | None = None
    gestational_week_target: int | None = None
    service_name: str | None = None

    model_config = {"from_attributes": True}


# ── ServicePackage ───────────────────────


class ServicePackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    total_price: float = Field(..., ge=0, description="Precio total del paquete en PEN")
    valid_from_week: int | None = Field(
        None, ge=1, le=42,
        description="Semana gestacional mínima para inscripción"
    )
    is_active: bool = True
    auto_schedule: bool = False
    items: list[PackageItemCreate] = Field(
        default_factory=list, description="Ítems del paquete"
    )


class ServicePackageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    total_price: float | None = Field(None, ge=0)
    valid_from_week: int | None = None
    is_active: bool | None = None
    auto_schedule: bool | None = None
    items: list[PackageItemCreate] | None = Field(
        None, description="Si se envía, reemplaza todos los ítems"
    )


class ServicePackageResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    name: str
    description: str | None = None
    total_price: float
    valid_from_week: int | None = None
    is_active: bool
    auto_schedule: bool
    items: list[PackageItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServicePackageListResponse(BaseModel):
    items: list[ServicePackageResponse]
    total: int
    page: int
    size: int
    pages: int
