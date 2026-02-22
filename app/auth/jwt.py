"""
Gestión de JWT con RS256 (claves asimétricas).
Access tokens (15 min) + Refresh tokens (7 días).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.config import get_settings

settings = get_settings()


class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"
    MFA_TEMP = "mfa_temp"


def create_access_token(
    user_id: UUID,
    clinic_id: UUID,
    role: str,
    extra_claims: dict | None = None,
) -> str:
    """Crea un access token JWT RS256 (corta duración)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "clinic_id": str(clinic_id),
        "role": role,
        "type": TokenType.ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: UUID, clinic_id: UUID) -> str:
    """Crea un refresh token JWT RS256 (larga duración)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "clinic_id": str(clinic_id),
        "type": TokenType.REFRESH,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    }

    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_mfa_temp_token(user_id: UUID, clinic_id: UUID) -> str:
    """Crea un token temporal para completar el flujo MFA (5 minutos)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "clinic_id": str(clinic_id),
        "type": TokenType.MFA_TEMP,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }

    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """
    Decodifica y verifica un token JWT.
    Lanza jwt.InvalidTokenError si el token es inválido o expirado.
    """
    return jwt.decode(
        token,
        settings.jwt_public_key,
        algorithms=[settings.JWT_ALGORITHM],
    )


def decode_token_safe(token: str) -> dict | None:
    """Decodifica un token JWT sin lanzar excepciones."""
    try:
        return decode_token(token)
    except jwt.InvalidTokenError:
        return None
