"""
Schemas para BankReconciliation — Conciliación bancaria.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.bank_reconciliation import ReconciliationStatus


class BankReconciliationCreate(BaseModel):
    cash_movement_id: UUID
    expected_amount: Decimal = Field(..., gt=0, decimal_places=2)
    bank_reference: str | None = Field(None, max_length=200)
    notes: str | None = None


class BankReconciliationReconcile(BaseModel):
    """Para conciliar: se provee el monto real."""
    actual_amount: Decimal = Field(..., ge=0, decimal_places=2)
    bank_reference: str | None = Field(None, max_length=200)
    notes: str | None = None


class BankReconciliationResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    cash_movement_id: UUID
    expected_amount: Decimal
    actual_amount: Decimal | None = None
    status: ReconciliationStatus
    bank_reference: str | None = None
    reconciled_at: datetime | None = None
    reconciled_by: UUID | None = None
    notes: str | None = None
    created_at: datetime
    difference: Decimal | None = None

    model_config = {"from_attributes": True}


class ReconciliationSummary(BaseModel):
    """Resumen de conciliación por período."""
    total_pending: int = 0
    total_matched: int = 0
    total_discrepancy: int = 0
    total_expected: Decimal = Decimal("0.00")
    total_actual: Decimal = Decimal("0.00")
    total_difference: Decimal = Decimal("0.00")
