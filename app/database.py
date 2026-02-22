"""
Configuración de base de datos con SQLAlchemy 2.0 async.
Incluye setup de RLS (Row-Level Security) para multi-tenancy.
"""

from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.config import get_settings

settings = get_settings()

# ── Engine async ─────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# ── Session factory ──────────────────────────────────
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base declarativa ─────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── RLS: setear tenant en la sesión ──────────────────
async def set_tenant_context(session: AsyncSession, clinic_id: UUID) -> None:
    """
    Setea la variable de sesión de PostgreSQL `app.clinic_id`
    para que las políticas RLS filtren automáticamente por clínica.
    """
    validated_clinic_id = UUID(str(clinic_id))
    await session.execute(
    text(f"SET LOCAL app.clinic_id = '{validated_clinic_id}'")
)


# ── Dependency: sesión de DB ─────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency de FastAPI que provee una sesión de base de datos.
    El tenant context se setea en el middleware de autenticación.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
