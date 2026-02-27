"""
Endpoints para Conciliación Bancaria (Yape, transferencias).
Crear, listar, conciliar pagos digitales.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.bank_reconciliation import ReconciliationStatus
from app.models.user import User, UserRole
from app.schemas.bank_reconciliation import (
    BankReconciliationCreate,
    BankReconciliationReconcile,
    BankReconciliationResponse,
    ReconciliationSummary,
)
from app.services import bank_reconciliation_service

router = APIRouter()

_ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)


@router.post("/", response_model=BankReconciliationResponse, status_code=201)
async def create_reconciliation(
    data: BankReconciliationCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un registro de conciliación pendiente. Solo admin."""
    return await bank_reconciliation_service.create_reconciliation(
        db, clinic_id=user.clinic_id, data=data
    )


@router.get("/", response_model=dict)
async def list_reconciliations(
    status: ReconciliationStatus | None = Query(None, description="Filtrar por estado"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista registros de conciliación con paginación."""
    return await bank_reconciliation_service.list_reconciliations(
        db, clinic_id=user.clinic_id, status=status, page=page, size=size
    )


@router.post("/{recon_id}/reconcile", response_model=BankReconciliationResponse)
async def reconcile(
    recon_id: UUID,
    data: BankReconciliationReconcile,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Concilia un pago: ingresa monto real y compara con esperado."""
    return await bank_reconciliation_service.reconcile(
        db, clinic_id=user.clinic_id, recon_id=recon_id,
        user_id=user.id, data=data
    )


@router.get("/summary", response_model=ReconciliationSummary)
async def get_summary(
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Resumen de conciliación: pendientes, coincidentes, discrepancias."""
    return await bank_reconciliation_service.get_summary(
        db, clinic_id=user.clinic_id
    )
