"""
Schemas para Clinic (tenant).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClinicBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    ruc: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    specialty_type: str | None = Field(None, max_length=100)
    timezone: str = Field(default="America/Lima", max_length=50)


class ClinicUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    specialty_type: str | None = Field(None, max_length=100)
    timezone: str | None = Field(None, max_length=50)
    logo_url: str | None = Field(None, max_length=500)
    settings: dict | None = None


class BillingConfigUpdate(BaseModel):
    """Configuración de facturación NubeFact para la clínica."""
    nubefact_token: str = Field(
        ..., min_length=10, max_length=500,
        description="Token de API NubeFact para esta clínica/RUC"
    )


class BillingConfigResponse(BaseModel):
    """Respuesta con la configuración de billing (token ofuscado)."""
    nubefact_token_configured: bool = False
    nubefact_token_preview: str | None = Field(
        None, description="Últimos 8 caracteres del token (ofuscado)"
    )


class ClinicResponse(ClinicBase):
    id: UUID
    slug: str | None = None
    logo_url: str | None = None
    settings: dict | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
