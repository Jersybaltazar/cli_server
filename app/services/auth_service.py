"""
Servicio de autenticación: registro, login, refresh, MFA.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    create_access_token,
    create_mfa_temp_token,
    create_refresh_token,
    decode_token,
    TokenType,
)
from app.core.exceptions import (
    ConflictException,
    CredentialsException,
    NotFoundException,
    ValidationException,
)
from app.core.security import hash_password, verify_password
from app.models.clinic import Clinic
from app.models.organization import Organization, PlanType
from app.models.user import User, UserRole
from app.models.user_clinic_access import UserClinicAccess
from app.schemas.auth import (
    ClinicLoginData,
    ClinicRegisterRequest,
    LoginRequest,
    LoginResponse,
    MFASetupResponse,
    RegisterResponse,
    TokenData,
    TokenResponse,
    UserLoginData,
)
from app.services.audit_service import log_action


async def register_clinic(
    db: AsyncSession,
    data: ClinicRegisterRequest,
    ip_address: str | None = None,
) -> RegisterResponse:
    """
    Registra una nueva organización + clínica (sede principal) + usuario org_admin.
    Retorna tokens para auto-login inmediato.
    """
    # Verificar que el RUC no exista
    existing_clinic = await db.execute(
        select(Clinic).where(Clinic.ruc == data.ruc)
    )
    if existing_clinic.scalar_one_or_none():
        raise ConflictException("Ya existe una clínica con ese RUC")

    # Verificar que el email no exista
    existing_user = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing_user.scalar_one_or_none():
        raise ConflictException("Ya existe un usuario con ese email")

    # 1. Crear Organization
    organization = Organization(
        name=data.organization_name or data.clinic_name,
        ruc=data.ruc,
        plan_type=PlanType.BASIC,
        max_clinics=1,
        contact_email=data.email,
    )
    db.add(organization)
    await db.flush()

    # 2. Crear Clinic (sede principal) vinculada a la org
    # Generate unique slug
    base_slug = Clinic.generate_slug(data.clinic_name)
    slug = base_slug
    suffix = 2
    while True:
        existing_slug = await db.execute(
            select(Clinic).where(Clinic.slug == slug)
        )
        if not existing_slug.scalar_one_or_none():
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    clinic = Clinic(
        name=data.clinic_name,
        ruc=data.ruc,
        phone=data.clinic_phone,
        address=data.clinic_address,
        specialty_type=data.specialty_type,
        branch_name="Sede Principal",
        organization_id=organization.id,
        slug=slug,
    )
    db.add(clinic)
    await db.flush()

    # 3. Crear User con rol org_admin
    user = User(
        clinic_id=clinic.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.ORG_ADMIN,
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()

    # 4. Crear UserClinicAccess
    access = UserClinicAccess(
        user_id=user.id,
        clinic_id=clinic.id,
        role_in_clinic=UserRole.ORG_ADMIN,
    )
    db.add(access)
    await db.flush()

    # Registrar en audit log
    await log_action(
        db,
        clinic_id=clinic.id,
        user_id=user.id,
        entity="organization",
        entity_id=str(organization.id),
        action="create",
        new_data={
            "organization": organization.name,
            "clinic": clinic.name,
            "ruc": clinic.ruc,
        },
        ip_address=ip_address,
    )

    # 5. Generar tokens para auto-login
    access_token = create_access_token(user.id, clinic.id, user.role.value)
    refresh_token = create_refresh_token(user.id, clinic.id)

    return RegisterResponse(
        organization_id=organization.id,
        clinic_id=clinic.id,
        user_id=user.id,
        email=user.email,
        tokens=TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
        ),
        user=UserLoginData(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role=user.role,
            is_mfa_enabled=user.is_mfa_enabled,
        ),
        clinic=ClinicLoginData(
            id=clinic.id,
            name=clinic.name,
            branch_name=clinic.branch_name,
            display_name=clinic.display_name,
            ruc=clinic.ruc,
            organization_id=organization.id,
            specialty_type=clinic.specialty_type,
            logo_url=clinic.logo_url,
        ),
    )


async def login(
    db: AsyncSession,
    data: LoginRequest,
    ip_address: str | None = None,
) -> LoginResponse:
    """
    Autentica un usuario con email y contraseña.
    Si tiene MFA habilitado, retorna un token temporal.
    """
    # Buscar usuario con su clínica
    result = await db.execute(
        select(User).where(User.email == data.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("Login fallido: usuario no encontrado para email=%s", data.email)
        raise CredentialsException("Email o contraseña incorrectos")

    if not verify_password(data.password, user.hashed_password):
        logger.warning(
            "Login fallido: contraseña incorrecta para user_id=%s email=%s clinic_id=%s",
            user.id, user.email, user.clinic_id,
        )
        raise CredentialsException("Email o contraseña incorrectos")

    # Cargar la clínica
    await db.refresh(user, ["clinic"])

    if not user.clinic:
        raise NotFoundException("Clínica no encontrada")

    # Si tiene MFA habilitado, retornar respuesta MFA
    if user.is_mfa_enabled and user.mfa_secret:
        temp_token = create_mfa_temp_token(user.id, user.clinic_id)
        return LoginResponse(
            user=UserLoginData(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                full_name=user.full_name,
                role=user.role,
                is_mfa_enabled=user.is_mfa_enabled,
            ),
            clinic=ClinicLoginData(
                id=user.clinic.id,
                name=user.clinic.name,
                branch_name=user.clinic.branch_name,
                display_name=user.clinic.display_name,
                ruc=user.clinic.ruc,
                organization_id=user.clinic.organization_id,
                specialty_type=user.clinic.specialty_type,
                logo_url=user.clinic.logo_url,
            ),
            tokens=TokenData(
                access_token="",
                refresh_token="",
                token_type=temp_token,
            ),
            requires_mfa=True,
        )

    # Actualizar último login
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    # Registrar en audit log
    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="user",
        entity_id=str(user.id),
        action="login",
        ip_address=ip_address,
    )

    # Generar tokens
    access_token = create_access_token(user.id, user.clinic_id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.clinic_id)

    return LoginResponse(
        user=UserLoginData(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role=user.role,
            is_mfa_enabled=user.is_mfa_enabled,
        ),
        clinic=ClinicLoginData(
            id=user.clinic.id,
            name=user.clinic.name,
            branch_name=user.clinic.branch_name,
            display_name=user.clinic.display_name,
            ruc=user.clinic.ruc,
            organization_id=user.clinic.organization_id,
            specialty_type=user.clinic.specialty_type,
            logo_url=user.clinic.logo_url,
        ),
        tokens=TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
        ),
    )


async def verify_mfa(
    db: AsyncSession,
    temp_token: str,
    code: str,
    ip_address: str | None = None,
) -> TokenResponse:
    """Verifica el código MFA/TOTP y emite tokens definitivos."""
    try:
        payload = decode_token(temp_token)
    except Exception:
        raise CredentialsException("Token MFA inválido o expirado")

    if payload.get("type") != TokenType.MFA_TEMP:
        raise CredentialsException("Token MFA inválido")

    user_id = UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.mfa_secret:
        raise CredentialsException("Usuario no encontrado")

    # Verificar TOTP
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        raise CredentialsException("Código MFA incorrecto")

    # Actualizar último login
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="user",
        entity_id=str(user.id),
        action="login_mfa",
        ip_address=ip_address,
    )

    access_token = create_access_token(user.id, user.clinic_id, user.role.value)
    refresh_token = create_refresh_token(user.id, user.clinic_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> TokenResponse:
    """Refresca un par de tokens usando el refresh token."""
    try:
        payload = decode_token(refresh_token_str)
    except Exception:
        raise CredentialsException("Refresh token inválido o expirado")

    if payload.get("type") != TokenType.REFRESH:
        raise CredentialsException("Token no es un refresh token")

    user_id = UUID(payload["sub"])
    clinic_id = UUID(payload["clinic_id"])

    # Verificar que el usuario sigue activo
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise CredentialsException("Usuario no encontrado o inactivo")

    access_token = create_access_token(user.id, clinic_id, user.role.value)
    new_refresh_token = create_refresh_token(user.id, clinic_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


async def setup_mfa(db: AsyncSession, user: User) -> MFASetupResponse:
    """Genera el secreto TOTP y la URI para el QR."""
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.is_mfa_enabled = True
    await db.flush()

    totp = pyotp.TOTP(secret)
    qr_uri = totp.provisioning_uri(
        name=user.email,
        issuer_name="SaaS Clínicas",
    )

    return MFASetupResponse(secret=secret, qr_uri=qr_uri)


async def disable_mfa(db: AsyncSession, user: User) -> None:
    """Desactiva MFA para un usuario."""
    user.mfa_secret = None
    user.is_mfa_enabled = False
    await db.flush()


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    ip_address: str | None = None,
) -> None:
    """Cambia la contraseña del usuario autenticado."""
    if not verify_password(current_password, user.hashed_password):
        raise CredentialsException("La contraseña actual es incorrecta")

    user.hashed_password = hash_password(new_password)
    await db.flush()

    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="user",
        entity_id=str(user.id),
        action="change_password",
        ip_address=ip_address,
    )
