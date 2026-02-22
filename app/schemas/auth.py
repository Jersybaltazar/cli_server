"""
Schemas de autenticación: login, registro, tokens, MFA.
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


# ── Login ────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserLoginData(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    is_mfa_enabled: bool


class ClinicLoginData(BaseModel):
    id: UUID
    name: str
    branch_name: str | None = None
    display_name: str | None = None
    ruc: str
    organization_id: UUID | None = None
    specialty_type: str | None = None
    logo_url: str | None = None


class LoginResponse(BaseModel):
    user: UserLoginData
    clinic: ClinicLoginData
    tokens: TokenData
    requires_mfa: bool = False


# ── MFA ──────────────────────────────────────────────
class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
    temp_token: str


class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str


# ── Refresh Token ────────────────────────────────────
class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── Registro de clínica + admin ──────────────────────
class ClinicRegisterRequest(BaseModel):
    """Registro inicial: crea organización + clínica + usuario org_admin."""

    # Datos de la organización (opcional)
    organization_name: str | None = Field(
        None,
        max_length=200,
        description="Nombre del grupo empresarial. Si no se provee, se usa clinic_name",
    )

    # Datos de la clínica
    clinic_name: str = Field(..., min_length=2, max_length=200)
    ruc: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    clinic_phone: str | None = Field(None, max_length=20)
    clinic_address: str | None = Field(None, max_length=500)
    specialty_type: str | None = Field(None, max_length=100)

    # Datos del usuario admin
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    phone: str | None = Field(None, max_length=20)


# ── Cambio de contraseña ────────────────────────────
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    message: str = "Contraseña actualizada correctamente"


class RegisterResponse(BaseModel):
    organization_id: UUID
    clinic_id: UUID
    user_id: UUID
    email: str
    tokens: TokenData
    user: UserLoginData
    clinic: ClinicLoginData
    message: str = "Registro exitoso"
