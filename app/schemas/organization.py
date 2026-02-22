"""
Schemas Pydantic para Organization (gestión multi-sede).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.organization import PlanType


# ── Organization ─────────────────────────────────────

class OrganizationCreate(BaseModel):
    """Crear una nueva organización."""
    name: str = Field(..., min_length=2, max_length=200, description="Nombre del grupo empresarial")
    ruc: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$", description="RUC de la organización")
    plan_type: PlanType = Field(default=PlanType.BASIC, description="Plan de suscripción")
    max_clinics: int = Field(default=1, ge=1, description="Máximo de sedes permitidas")
    contact_email: str | None = None
    contact_phone: str | None = None


class OrganizationUpdate(BaseModel):
    """Actualizar una organización existente."""
    name: str | None = Field(None, min_length=2, max_length=200)
    plan_type: PlanType | None = None
    max_clinics: int | None = Field(None, ge=1)
    contact_email: str | None = None
    contact_phone: str | None = None
    is_active: bool | None = None


class OrganizationResponse(BaseModel):
    """Respuesta de organización."""
    id: uuid.UUID
    name: str
    ruc: str
    plan_type: PlanType
    max_clinics: int
    contact_email: str | None = None
    contact_phone: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationWithClinicsResponse(OrganizationResponse):
    """Respuesta de organización con sus clínicas."""
    clinics: list["ClinicBranchResponse"] = []


# ── Clinic Branch (para respuestas de org) ───────────

class ClinicBranchResponse(BaseModel):
    """Respuesta resumida de una sede/sucursal."""
    id: uuid.UUID
    name: str
    branch_name: str | None = None
    address: str | None = None
    phone: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Agregar sede ────────────────────────────────────

class AddClinicToOrgRequest(BaseModel):
    """Agregar una clínica existente o crear nueva sede en la organización."""
    clinic_id: uuid.UUID | None = Field(None, description="ID de clínica existente para vincular")
    name: str | None = Field(None, min_length=2, max_length=200, description="Nombre para nueva sede")
    branch_name: str | None = Field(None, max_length=100, description="Nombre de la sucursal")
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    specialty_type: str | None = None


# ── Acceso multi-sede ────────────────────────────────

class UserClinicAccessCreate(BaseModel):
    """Otorgar acceso a un usuario a una sede."""
    user_id: uuid.UUID = Field(..., description="ID del usuario")
    clinic_id: uuid.UUID = Field(..., description="ID de la sede")
    role_in_clinic: str = Field(..., description="Rol del usuario en esta sede")


class UserClinicAccessResponse(BaseModel):
    """Respuesta de acceso de usuario a sede."""
    id: uuid.UUID
    user_id: uuid.UUID
    clinic_id: uuid.UUID
    role_in_clinic: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Switch de sede ───────────────────────────────────

class SwitchClinicRequest(BaseModel):
    """Request para cambiar de sede activa."""
    clinic_id: uuid.UUID = Field(..., description="ID de la sede a la que cambiar")


class SwitchClinicResponse(BaseModel):
    """Tokens nuevos con la sede seleccionada."""
    access_token: str
    refresh_token: str
    clinic_id: uuid.UUID
    clinic_name: str
