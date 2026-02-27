"""
Schemas para ServicePriceVariant — Variantes de precio de servicios.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.service_variant import ModifierType


class ServiceVariantCreate(BaseModel):
    service_id: UUID
    label: str = Field(..., max_length=100)
    modifier_type: ModifierType
    modifier_value: Decimal = Field(..., gt=0, decimal_places=2)


class ServiceVariantUpdate(BaseModel):
    label: str | None = Field(None, max_length=100)
    modifier_type: ModifierType | None = None
    modifier_value: Decimal | None = Field(None, gt=0, decimal_places=2)
    is_active: bool | None = None


class ServiceVariantResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    service_id: UUID
    label: str
    modifier_type: ModifierType
    modifier_value: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Enriquecido
    service_name: str | None = None
    calculated_price: Decimal | None = None

    model_config = {"from_attributes": True}
