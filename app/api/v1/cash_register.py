"""
Endpoints de Caja — Sesiones y Movimientos.
Apertura/cierre de caja diaria, registro de ingresos y egresos.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.cash_register import (
    CashSessionStatus,
    MovementCategory,
    MovementType,
)
from app.models.user import User, UserRole
from app.schemas.cash_register import (
    CashMovementCreate,
    CashMovementListResponse,
    CashMovementResponse,
    CashSessionClose,
    CashSessionListResponse,
    CashSessionOpen,
    CashSessionResponse,
    DailyCashSummary,
)
from app.services import cash_register_service

router = APIRouter()

_CASH_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
    UserRole.DOCTOR,
)


# ── Sessions ──────────────────────────────────────────


@router.get("/sessions/current", response_model=CashSessionResponse | None)
async def get_current_session(
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Retorna la sesión de caja abierta (o null si no hay)."""
    return await cash_register_service.get_open_session(db, user.clinic_id)


@router.post("/sessions", response_model=CashSessionResponse, status_code=201)
async def open_session(
    data: CashSessionOpen,
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Abre una nueva sesión de caja con fondo inicial."""
    return await cash_register_service.open_session(
        db, user.clinic_id, user.id, data
    )


@router.get("/sessions", response_model=CashSessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: CashSessionStatus | None = Query(None),
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista sesiones de caja con paginación y filtro de estado."""
    return await cash_register_service.list_sessions(
        db, user.clinic_id, page, size, status
    )


@router.post("/sessions/{session_id}/close", response_model=CashSessionResponse)
async def close_session(
    session_id: UUID,
    data: CashSessionClose,
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Cierra una sesión de caja con cuadre de montos."""
    return await cash_register_service.close_session(
        db, user.clinic_id, user.id, session_id, data
    )


@router.get("/sessions/{session_id}/summary", response_model=DailyCashSummary)
async def get_session_summary(
    session_id: UUID,
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el resumen agregado de una sesión de caja."""
    return await cash_register_service.get_daily_summary(
        db, user.clinic_id, session_id
    )


# ── Movements ─────────────────────────────────────────


@router.post("/movements", response_model=CashMovementResponse, status_code=201)
async def create_movement(
    data: CashMovementCreate,
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Registra un movimiento de ingreso o egreso en la caja abierta."""
    return await cash_register_service.create_movement(
        db, user.clinic_id, user.id, data
    )


@router.get("/movements", response_model=CashMovementListResponse)
async def list_movements(
    session_id: UUID | None = Query(None, description="Filtrar por sesión"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    movement_type: MovementType | None = Query(None),
    category: MovementCategory | None = Query(None),
    user: User = Depends(require_role(*_CASH_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista movimientos de caja con filtros opcionales."""
    return await cash_register_service.list_movements(
        db, user.clinic_id, session_id, page, size, movement_type, category
    )
