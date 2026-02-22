"""
Schemas para User.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.RECEPTIONIST
    cmp_number: str | None = Field(None, max_length=20)
    specialty: str | None = Field(None, max_length=100)
    specialty_type: str | None = Field(None, max_length=100)
    position: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    target_clinic_id: UUID | None = Field(
        None,
        description=(
            "Sede destino para el nuevo usuario. "
            "Solo org_admin/super_admin pueden asignar a otra sede. "
            "Debe pertenecer a la misma organización. "
            "Si no se envía, se usa la sede del admin que crea."
        ),
    )


class UserUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    role: UserRole | None = None
    cmp_number: str | None = None
    specialty: str | None = None
    specialty_type: str | None = None
    position: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    cmp_number: str | None = None
    specialty: str | None = None
    specialty_type: str | None = None
    position: str | None = None
    phone: str | None = None
    is_mfa_enabled: bool
    is_active: bool
    last_login: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserMe(BaseModel):
    """Respuesta para el endpoint /me con datos de la clínica."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    clinic_id: UUID
    clinic_name: str | None = None
    is_mfa_enabled: bool

    model_config = {"from_attributes": True}
