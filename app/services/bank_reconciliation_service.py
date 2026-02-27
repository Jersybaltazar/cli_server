"""
Servicio de Conciliación Bancaria — CRUD + conciliación + resumen.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ConflictException
from app.models.bank_reconciliation import BankReconciliation, ReconciliationStatus
from app.schemas.bank_reconciliation import (
    BankReconciliationCreate,
    BankReconciliationReconcile,
    BankReconciliationResponse,
    ReconciliationSummary,
)


def _to_response(recon: BankReconciliation) -> BankReconciliationResponse:
    difference = None
    if recon.actual_amount is not None:
        difference = recon.actual_amount - recon.expected_amount
    return BankReconciliationResponse(
        id=recon.id,
        clinic_id=recon.clinic_id,
        cash_movement_id=recon.cash_movement_id,
        expected_amount=recon.expected_amount,
        actual_amount=recon.actual_amount,
        status=recon.status,
        bank_reference=recon.bank_reference,
        reconciled_at=recon.reconciled_at,
        reconciled_by=recon.reconciled_by,
        notes=recon.notes,
        created_at=recon.created_at,
        difference=difference,
    )


async def create_reconciliation(
    db: AsyncSession,
    clinic_id: UUID,
    data: BankReconciliationCreate,
) -> BankReconciliationResponse:
    """Crea un registro de conciliación pendiente."""
    recon = BankReconciliation(
        clinic_id=clinic_id,
        cash_movement_id=data.cash_movement_id,
        expected_amount=data.expected_amount,
        bank_reference=data.bank_reference,
        notes=data.notes,
    )
    db.add(recon)
    await db.commit()
    await db.refresh(recon)
    return _to_response(recon)


async def list_reconciliations(
    db: AsyncSession,
    clinic_id: UUID,
    status: ReconciliationStatus | None = None,
    page: int = 1,
    size: int = 50,
) -> dict:
    """Lista registros de conciliación con paginación."""
    query = select(BankReconciliation).where(
        BankReconciliation.clinic_id == clinic_id
    )
    if status:
        query = query.where(BankReconciliation.status == status)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated
    query = query.order_by(BankReconciliation.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [_to_response(r) for r in items],
        "total": total,
        "page": page,
        "size": size,
    }


async def reconcile(
    db: AsyncSession,
    clinic_id: UUID,
    recon_id: UUID,
    user_id: UUID,
    data: BankReconciliationReconcile,
) -> BankReconciliationResponse:
    """Concilia un registro: compara monto real vs esperado."""
    result = await db.execute(
        select(BankReconciliation).where(
            BankReconciliation.id == recon_id,
            BankReconciliation.clinic_id == clinic_id,
        )
    )
    recon = result.scalar_one_or_none()
    if not recon:
        raise NotFoundException("Registro de conciliación no encontrado")

    if recon.status != ReconciliationStatus.PENDING:
        raise ConflictException("Este registro ya fue conciliado")

    recon.actual_amount = data.actual_amount
    recon.reconciled_at = datetime.now(timezone.utc)
    recon.reconciled_by = user_id

    if data.bank_reference:
        recon.bank_reference = data.bank_reference
    if data.notes:
        recon.notes = data.notes

    # Determinar status
    if recon.actual_amount == recon.expected_amount:
        recon.status = ReconciliationStatus.MATCHED
    else:
        recon.status = ReconciliationStatus.DISCREPANCY

    await db.commit()
    await db.refresh(recon)
    return _to_response(recon)


async def get_summary(
    db: AsyncSession,
    clinic_id: UUID,
) -> ReconciliationSummary:
    """Resumen de conciliación."""
    base = BankReconciliation.clinic_id == clinic_id

    pending = await db.scalar(
        select(func.count()).where(base, BankReconciliation.status == ReconciliationStatus.PENDING)
    ) or 0
    matched = await db.scalar(
        select(func.count()).where(base, BankReconciliation.status == ReconciliationStatus.MATCHED)
    ) or 0
    discrepancy = await db.scalar(
        select(func.count()).where(base, BankReconciliation.status == ReconciliationStatus.DISCREPANCY)
    ) or 0

    total_expected = Decimal(str(
        await db.scalar(
            select(func.coalesce(func.sum(BankReconciliation.expected_amount), 0)).where(base)
        ) or 0
    ))
    total_actual = Decimal(str(
        await db.scalar(
            select(func.coalesce(func.sum(BankReconciliation.actual_amount), 0)).where(
                base, BankReconciliation.actual_amount.isnot(None)
            )
        ) or 0
    ))

    return ReconciliationSummary(
        total_pending=pending,
        total_matched=matched,
        total_discrepancy=discrepancy,
        total_expected=total_expected,
        total_actual=total_actual,
        total_difference=total_actual - total_expected,
    )
