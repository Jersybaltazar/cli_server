"""
Schemas para ProcedureSupply — Mapeo servicio → insumos consumidos.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProcedureSupplyCreate(BaseModel):
    service_id: UUID
    item_id: UUID
    quantity: Decimal = Field(default=1, gt=0, decimal_places=2)


class ProcedureSupplyUpdate(BaseModel):
    quantity: Decimal | None = Field(None, gt=0, decimal_places=2)
    is_active: bool | None = None


class ProcedureSupplyResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    service_id: UUID
    item_id: UUID
    quantity: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcedureSupplyWithNames(ProcedureSupplyResponse):
    """Response enriquecido con nombres de servicio e insumo."""
    service_name: str | None = None
    item_name: str | None = None
    item_code: str | None = None
    item_unit: str | None = None
