"""Schemas Pydantic v2 para PatientPackage y PackagePayment."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.cash_register import PaymentMethod
from app.models.patient_package import PatientPackageStatus


# ── PackagePayment ───────────────────────


class PackagePaymentCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Monto del pago en PEN")
    payment_method: PaymentMethod = PaymentMethod.CASH
    cash_movement_id: UUID | None = None
    invoice_id: UUID | None = None
    notes: str | None = None


class PackagePaymentResponse(BaseModel):
    id: UUID
    patient_package_id: UUID
    clinic_id: UUID
    amount: float
    payment_method: PaymentMethod
    cash_movement_id: UUID | None = None
    invoice_id: UUID | None = None
    notes: str | None = None
    created_by: UUID
    paid_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Embeds para el paquete inscrito ──────


class PackageItemEmbed(BaseModel):
    """Ítem de paquete embebido en la respuesta de inscripción."""
    id: UUID
    service_id: UUID
    quantity: int
    description_override: str | None = None
    gestational_week_target: int | None = None
    service_name: str | None = None


class PackageEmbed(BaseModel):
    """Datos del paquete embebidos en la respuesta de inscripción."""
    id: UUID
    name: str
    auto_schedule: bool
    items: list[PackageItemEmbed] = []


# ── PatientPackage ───────────────────────


class PatientPackageEnroll(BaseModel):
    """Inscripción de paciente en paquete."""
    patient_id: UUID
    package_id: UUID
    initial_payment: float | None = Field(
        None, ge=0, description="Pago inicial al inscribir"
    )
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: str | None = None


class PatientPackageResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    package_id: UUID
    enrolled_by: UUID
    total_amount: float
    amount_paid: float
    balance: float
    status: PatientPackageStatus
    notes: str | None = None
    enrolled_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Datos expandidos
    package_name: str | None = None
    patient_name: str | None = None
    package: PackageEmbed | None = None
    payments: list[PackagePaymentResponse] = []

    model_config = {"from_attributes": True}


class PatientPackageListResponse(BaseModel):
    items: list[PatientPackageResponse]
    total: int
    page: int
    size: int
    pages: int
