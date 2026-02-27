"""Schemas Pydantic v2 para CommissionRule y CommissionEntry."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.commission import CommissionEntryStatus, CommissionType


# ── CommissionRule ───────────────────────


class CommissionRuleCreate(BaseModel):
    doctor_id: UUID | None = Field(
        None, description="Null = regla default para todos los doctores"
    )
    service_id: UUID
    commission_type: CommissionType
    value: float = Field(..., ge=0, description="Porcentaje (0-100) o monto fijo")
    is_active: bool = True


class CommissionRuleUpdate(BaseModel):
    commission_type: CommissionType | None = None
    value: float | None = Field(None, ge=0)
    is_active: bool | None = None


class CommissionRuleResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID | None = None
    service_id: UUID
    commission_type: CommissionType
    value: float
    is_active: bool
    service_name: str | None = None
    doctor_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── CommissionEntry ──────────────────────


class CommissionEntryResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    appointment_id: UUID | None = None
    service_id: UUID
    patient_id: UUID
    service_amount: float
    commission_amount: float
    status: CommissionEntryStatus
    period: str
    paid_at: datetime | None = None
    paid_reference: str | None = None
    created_at: datetime

    # Datos expandidos
    doctor_name: str | None = None
    service_name: str | None = None
    patient_name: str | None = None

    model_config = {"from_attributes": True}


class CommissionEntryListResponse(BaseModel):
    items: list[CommissionEntryResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Liquidación ──────────────────────────


class DoctorLiquidation(BaseModel):
    doctor_id: UUID
    doctor_name: str
    total_services: int
    total_service_amount: float
    total_commission: float
    pending_amount: float
    paid_amount: float
    entries: list[CommissionEntryResponse] = []


class LiquidationResponse(BaseModel):
    period: str
    clinic_id: UUID
    doctors: list[DoctorLiquidation]
    grand_total_commission: float
    grand_total_pending: float
    grand_total_paid: float


# ── Mark as paid ─────────────────────────


class CommissionMarkPaid(BaseModel):
    entry_ids: list[UUID] = Field(..., min_length=1)
    paid_reference: str | None = None
