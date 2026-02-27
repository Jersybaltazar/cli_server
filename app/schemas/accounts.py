"""Schemas Pydantic v2 para Cuentas por Cobrar y Pagar."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.accounts import AccountStatus
from app.models.cash_register import PaymentMethod


# ── Payments (compartido) ────────────────


class AccountPaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethod = PaymentMethod.CASH
    cash_movement_id: UUID | None = None
    notes: str | None = None


class AccountPaymentResponse(BaseModel):
    id: UUID
    amount: float
    payment_method: PaymentMethod
    cash_movement_id: UUID | None = None
    notes: str | None = None
    created_by: UUID
    paid_at: datetime

    model_config = {"from_attributes": True}


# ── Account Receivable ──────────────────


class ARCreate(BaseModel):
    patient_id: UUID
    description: str = Field(..., min_length=1, max_length=500)
    total_amount: float = Field(..., gt=0)
    due_date: date | None = None
    reference_type: str | None = None
    reference_id: UUID | None = None


class ARResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    description: str
    total_amount: float
    amount_paid: float
    balance: float
    due_date: date | None = None
    reference_type: str | None = None
    reference_id: UUID | None = None
    status: AccountStatus
    created_at: datetime
    updated_at: datetime
    patient_name: str | None = None
    payments: list[AccountPaymentResponse] = []

    model_config = {"from_attributes": True}


class ARListResponse(BaseModel):
    items: list[ARResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Account Payable ─────────────────────


class APCreate(BaseModel):
    supplier_id: UUID | None = None
    description: str = Field(..., min_length=1, max_length=500)
    total_amount: float = Field(..., gt=0)
    due_date: date | None = None
    reference: str | None = None


class APResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    supplier_id: UUID | None = None
    description: str
    total_amount: float
    amount_paid: float
    balance: float
    due_date: date | None = None
    reference: str | None = None
    status: AccountStatus
    created_at: datetime
    updated_at: datetime
    supplier_name: str | None = None
    payments: list[AccountPaymentResponse] = []

    model_config = {"from_attributes": True}


class APListResponse(BaseModel):
    items: list[APResponse]
    total: int
    page: int
    size: int
    pages: int
