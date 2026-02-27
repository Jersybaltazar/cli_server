"""Endpoints REST para Cuentas por Cobrar y por Pagar."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.accounts import AccountStatus
from app.models.user import User, UserRole
from app.schemas.accounts import (
    AccountPaymentCreate,
    APCreate,
    APListResponse,
    APResponse,
    ARCreate,
    ARListResponse,
    ARResponse,
)
from app.services import accounts_service

router = APIRouter()

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
)

_FINANCE_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.RECEPTIONIST,
)


# ── Accounts Receivable ─────────────────


@router.get("/receivable", response_model=ARListResponse)
async def list_receivables(
    patient_id: UUID | None = Query(None),
    status: AccountStatus | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(*_FINANCE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista cuentas por cobrar."""
    return await accounts_service.list_receivables(
        db, clinic_id=user.clinic_id,
        patient_id=patient_id, status=status, page=page, size=size,
    )


@router.get("/receivable/{ar_id}", response_model=ARResponse)
async def get_receivable(
    ar_id: UUID,
    user: User = Depends(require_role(*_FINANCE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de una cuenta por cobrar con pagos."""
    return await accounts_service.get_receivable(
        db, clinic_id=user.clinic_id, ar_id=ar_id
    )


@router.post("/receivable", response_model=ARResponse, status_code=201)
async def create_receivable(
    data: ARCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea una cuenta por cobrar (solo admin)."""
    return await accounts_service.create_receivable(
        db, clinic_id=user.clinic_id, data=data
    )


@router.post("/receivable/{ar_id}/payments", response_model=ARResponse, status_code=201)
async def pay_receivable(
    ar_id: UUID,
    data: AccountPaymentCreate,
    user: User = Depends(require_role(*_FINANCE_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Registra pago en cuenta por cobrar."""
    return await accounts_service.pay_receivable(
        db, clinic_id=user.clinic_id, user=user, ar_id=ar_id, data=data
    )


# ── Accounts Payable ────────────────────


@router.get("/payable", response_model=APListResponse)
async def list_payables(
    status: AccountStatus | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista cuentas por pagar (solo admin)."""
    return await accounts_service.list_payables(
        db, clinic_id=user.clinic_id, status=status, page=page, size=size,
    )


@router.get("/payable/{ap_id}", response_model=APResponse)
async def get_payable(
    ap_id: UUID,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de una cuenta por pagar con pagos."""
    return await accounts_service.get_payable(
        db, clinic_id=user.clinic_id, ap_id=ap_id
    )


@router.post("/payable", response_model=APResponse, status_code=201)
async def create_payable(
    data: APCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea una cuenta por pagar (solo admin)."""
    return await accounts_service.create_payable(
        db, clinic_id=user.clinic_id, data=data
    )


@router.post("/payable/{ap_id}/payments", response_model=APResponse, status_code=201)
async def pay_payable(
    ap_id: UUID,
    data: AccountPaymentCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Registra pago en cuenta por pagar (solo admin)."""
    return await accounts_service.pay_payable(
        db, clinic_id=user.clinic_id, user=user, ap_id=ap_id, data=data
    )
