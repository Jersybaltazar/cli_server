"""
Dependencies de FastAPI para autenticación y contexto de tenant.
"""

from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TokenType, decode_token
from app.core.exceptions import CredentialsException, ForbiddenException
from app.database import get_db, set_tenant_context
from app.models.user import User, UserRole

# ── Security scheme ──────────────────────────────────
security = HTTPBearer()


# ── Token payload tipado ─────────────────────────────
class TokenPayload:
    """Datos extraídos del token JWT decodificado."""

    def __init__(self, payload: dict):
        self.user_id: UUID = UUID(payload["sub"])
        self.clinic_id: UUID = UUID(payload["clinic_id"])
        self.role: str = payload.get("role", "")
        self.token_type: str = payload.get("type", TokenType.ACCESS)


# ── Obtener usuario actual ───────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency que:
    1. Decodifica el JWT del header Authorization
    2. Carga el usuario de la DB
    3. Setea el contexto RLS de tenant
    """
    try:
        payload = decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise CredentialsException("Token inválido o expirado")

    token_data = TokenPayload(payload)

    # Verificar que es un access token
    if token_data.token_type != TokenType.ACCESS:
        raise CredentialsException("Tipo de token inválido")

    # Cargar usuario
    result = await db.execute(
        select(User).where(
            User.id == token_data.user_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise CredentialsException("Usuario no encontrado o inactivo")

    # Setear contexto RLS para multi-tenancy
    await set_tenant_context(db, user.clinic_id)

    return user


# ── Obtener solo el payload (sin consultar DB) ───────
async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """Dependency ligera: solo decodifica el token sin consultar la DB."""
    try:
        payload = decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise CredentialsException("Token inválido o expirado")
    return TokenPayload(payload)


# ── Factory de dependency con roles ──────────────────
def require_role(*allowed_roles: UserRole):
    """
    Factory que crea un dependency que verifica el rol del usuario.

    Uso:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.CLINIC_ADMIN))):
            ...
    """

    async def _check_role(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenException(
                f"Se requiere uno de los roles: {', '.join(r.value for r in allowed_roles)}"
            )
        return user

    return _check_role
