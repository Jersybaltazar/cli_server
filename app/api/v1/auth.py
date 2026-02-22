"""
Endpoints de autenticación: registro, login, refresh, MFA.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ClinicRegisterRequest,
    LoginRequest,
    LoginResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshRequest,
    RegisterResponse,
    TokenResponse,
)
from app.schemas.user import UserMe
from app.services import auth_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    """Obtiene la IP del cliente desde los headers o la conexión."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    data: ClinicRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Registra una nueva clínica y su usuario administrador.
    No requiere autenticación.
    """
    return await auth_service.register_clinic(
        db, data, ip_address=_get_client_ip(request)
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Autentica un usuario con email y contraseña.
    Si tiene MFA habilitado, retorna `requires_mfa=true` y un token temporal.
    """
    return await auth_service.login(
        db, data, ip_address=_get_client_ip(request)
    )


@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(
    data: MFAVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verifica el código MFA/TOTP y emite tokens definitivos."""
    return await auth_service.verify_mfa(
        db,
        temp_token=data.temp_token,
        code=data.code,
        ip_address=_get_client_ip(request),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresca un par de tokens usando el refresh token."""
    return await auth_service.refresh_tokens(db, data.refresh_token)


@router.get("/me", response_model=UserMe)
async def get_me(
    user: User = Depends(get_current_user),
):
    """Retorna los datos del usuario autenticado."""
    return UserMe(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        role=user.role,
        clinic_id=user.clinic_id,
        clinic_name=user.clinic.name if user.clinic else None,
        is_mfa_enabled=user.is_mfa_enabled,
    )


@router.put("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cambia la contraseña del usuario autenticado."""
    if data.new_password != data.confirm_password:
        from app.core.exceptions import ValidationException
        raise ValidationException("Las contraseñas no coinciden")

    await auth_service.change_password(
        db,
        user=user,
        current_password=data.current_password,
        new_password=data.new_password,
        ip_address=_get_client_ip(request),
    )
    await db.commit()
    return ChangePasswordResponse()


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Configura MFA/TOTP para el usuario autenticado. Retorna secreto y QR."""
    return await auth_service.setup_mfa(db, user)


@router.post("/mfa/disable", status_code=204)
async def disable_mfa(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Desactiva MFA para el usuario autenticado."""
    await auth_service.disable_mfa(db, user)
