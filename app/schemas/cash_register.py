"""
Schemas para CashSession y CashMovement — Control de Caja.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.cash_register import (
    CashSessionStatus,
    MovementCategory,
    MovementType,
    PaymentMethod,
)


# ── Session ───────────────────────────────────────────


class CashSessionOpen(BaseModel):
    """Request para abrir una sesión de caja."""
    opening_amount: Decimal = Field(..., ge=0, description="Monto de fondo inicial")
    notes: str | None = Field(None, max_length=2000)


class CashSessionClose(BaseModel):
    """Request para cerrar una sesión de caja."""
    actual_closing_amount: Decimal = Field(..., ge=0, description="Monto real contado")
    notes: str | None = Field(None, max_length=2000)


class CashSessionResponse(BaseModel):
    """Respuesta de una sesión de caja."""
    id: UUID
    clinic_id: UUID
    opened_by: UUID
    closed_by: UUID | None = None
    status: CashSessionStatus
    opening_amount: Decimal
    expected_closing_amount: Decimal | None = None
    actual_closing_amount: Decimal | None = None
    difference: Decimal | None = None
    total_income: Decimal = Decimal("0")
    total_expense: Decimal = Decimal("0")
    notes: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CashSessionListResponse(BaseModel):
    """Respuesta paginada de sesiones de caja."""
    items: list[CashSessionResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Movement ──────────────────────────────────────────


class CashMovementCreate(BaseModel):
    """Request para registrar un movimiento de caja."""
    movement_type: MovementType
    category: MovementCategory
    payment_method: PaymentMethod = PaymentMethod.CASH
    amount: Decimal = Field(..., gt=0, description="Monto (siempre positivo)")
    description: str = Field(..., min_length=2, max_length=500)
    reference: str | None = Field(None, max_length=100)
    invoice_id: UUID | None = None
    patient_id: UUID | None = None
    notes: str | None = Field(None, max_length=2000)


class CashMovementResponse(BaseModel):
    """Respuesta de un movimiento de caja."""
    id: UUID
    clinic_id: UUID
    session_id: UUID
    created_by: UUID
    movement_type: MovementType
    category: MovementCategory
    payment_method: PaymentMethod
    amount: Decimal
    description: str
    reference: str | None = None
    invoice_id: UUID | None = None
    patient_id: UUID | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CashMovementListResponse(BaseModel):
    """Respuesta paginada de movimientos de caja."""
    items: list[CashMovementResponse]
    total: int
    page: int
    size: int
    pages: int


# ── Summary ───────────────────────────────────────────


class DailyCashSummary(BaseModel):
    """Resumen de la sesión de caja."""
    session_id: UUID
    status: str
    opening_amount: Decimal
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
    income_by_method: dict[str, Decimal]
    expense_by_category: dict[str, Decimal]
    movement_count: int
