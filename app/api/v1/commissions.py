"""Endpoints REST para comisiones médicas."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.commission import CommissionEntryStatus
from app.models.user import User, UserRole
from app.schemas.commission import (
    CommissionEntryListResponse,
    CommissionMarkPaid,
    CommissionRuleCreate,
    CommissionRuleResponse,
    CommissionRuleUpdate,
    LiquidationResponse,
)
from app.services import commission_service

router = APIRouter()

_ADMIN_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
)

_VIEW_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)


# ── Rules ────────────────────────────────


@router.get("/rules", response_model=list[CommissionRuleResponse])
async def list_rules(
    doctor_id: UUID | None = Query(None),
    service_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista reglas de comisión (solo admin)."""
    return await commission_service.list_rules(
        db, clinic_id=user.clinic_id,
        doctor_id=doctor_id, service_id=service_id, is_active=is_active,
    )


@router.post("/rules", response_model=CommissionRuleResponse, status_code=201)
async def create_rule(
    data: CommissionRuleCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea una regla de comisión (solo admin)."""
    return await commission_service.create_rule(
        db, clinic_id=user.clinic_id, data=data
    )


@router.patch("/rules/{rule_id}", response_model=CommissionRuleResponse)
async def update_rule(
    rule_id: UUID,
    data: CommissionRuleUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza una regla de comisión (solo admin)."""
    return await commission_service.update_rule(
        db, clinic_id=user.clinic_id, rule_id=rule_id, data=data
    )


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: UUID,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Desactiva una regla de comisión (solo admin)."""
    await commission_service.delete_rule(
        db, clinic_id=user.clinic_id, rule_id=rule_id
    )


# ── Entries ──────────────────────────────


@router.get("/entries", response_model=CommissionEntryListResponse)
async def list_entries(
    doctor_id: UUID | None = Query(None),
    period: str | None = Query(None, description="Periodo YYYY-MM"),
    status: CommissionEntryStatus | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(*_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista entradas de comisión. Doctores solo ven las propias."""
    # Doctores/obstetras solo ven sus propias comisiones
    if user.role in (UserRole.DOCTOR, UserRole.OBSTETRA):
        doctor_id = user.id

    return await commission_service.list_entries(
        db, clinic_id=user.clinic_id,
        doctor_id=doctor_id, period=period, status=status,
        page=page, size=size,
    )


# ── Liquidación ──────────────────────────


@router.get("/liquidation", response_model=LiquidationResponse)
async def get_liquidation(
    period: str = Query(..., description="Periodo YYYY-MM"),
    doctor_id: UUID | None = Query(None),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Resumen de comisiones por doctor para un período (solo admin)."""
    return await commission_service.get_liquidation(
        db, clinic_id=user.clinic_id, period=period, doctor_id=doctor_id
    )


@router.post("/mark-paid")
async def mark_as_paid(
    data: CommissionMarkPaid,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Marca comisiones como pagadas (solo admin)."""
    count = await commission_service.mark_as_paid(
        db, clinic_id=user.clinic_id, data=data
    )
    return {"marked_paid": count}
