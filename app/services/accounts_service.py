"""
Lógica de negocio para Cuentas por Cobrar (AR) y por Pagar (AP).
CRUD + pagos parciales + actualización de status.
"""

import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, ValidationException
from app.models.accounts import (
    AccountPayable,
    AccountReceivable,
    AccountStatus,
    APPayment,
    ARPayment,
)
from app.models.user import User
from app.schemas.accounts import (
    AccountPaymentCreate,
    AccountPaymentResponse,
    APCreate,
    APListResponse,
    APResponse,
    ARCreate,
    ARListResponse,
    ARResponse,
)


# ── Helpers ──────────────────────────────


def _ar_to_response(ar: AccountReceivable) -> ARResponse:
    return ARResponse(
        id=ar.id,
        clinic_id=ar.clinic_id,
        patient_id=ar.patient_id,
        description=ar.description,
        total_amount=float(ar.total_amount),
        amount_paid=float(ar.amount_paid),
        balance=float(ar.balance),
        due_date=ar.due_date,
        reference_type=ar.reference_type,
        reference_id=ar.reference_id,
        status=ar.status,
        created_at=ar.created_at,
        updated_at=ar.updated_at,
        patient_name=ar.patient.full_name if ar.patient else None,
        payments=[
            AccountPaymentResponse(
                id=p.id, amount=float(p.amount),
                payment_method=p.payment_method,
                cash_movement_id=p.cash_movement_id,
                notes=p.notes, created_by=p.created_by, paid_at=p.paid_at,
            )
            for p in ar.payments
        ],
    )


def _ap_to_response(ap: AccountPayable) -> APResponse:
    return APResponse(
        id=ap.id,
        clinic_id=ap.clinic_id,
        supplier_id=ap.supplier_id,
        description=ap.description,
        total_amount=float(ap.total_amount),
        amount_paid=float(ap.amount_paid),
        balance=float(ap.balance),
        due_date=ap.due_date,
        reference=ap.reference,
        status=ap.status,
        created_at=ap.created_at,
        updated_at=ap.updated_at,
        supplier_name=ap.supplier.business_name if ap.supplier else None,
        payments=[
            AccountPaymentResponse(
                id=p.id, amount=float(p.amount),
                payment_method=p.payment_method,
                cash_movement_id=p.cash_movement_id,
                notes=p.notes, created_by=p.created_by, paid_at=p.paid_at,
            )
            for p in ap.payments
        ],
    )


def _update_status(account: AccountReceivable | AccountPayable) -> None:
    """Actualiza el status según amount_paid vs total_amount."""
    if account.amount_paid >= account.total_amount:
        account.status = AccountStatus.PAID
    elif account.amount_paid > 0:
        account.status = AccountStatus.PARTIAL
    else:
        account.status = AccountStatus.PENDING


# ── Account Receivable ──────────────────


async def create_receivable(
    db: AsyncSession,
    clinic_id: UUID,
    data: ARCreate,
) -> ARResponse:
    """Crea una cuenta por cobrar."""
    ar = AccountReceivable(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        description=data.description,
        total_amount=Decimal(str(data.total_amount)),
        amount_paid=Decimal("0.00"),
        due_date=data.due_date,
        reference_type=data.reference_type,
        reference_id=data.reference_id,
        status=AccountStatus.PENDING,
    )
    db.add(ar)
    await db.commit()
    return await get_receivable(db, clinic_id, ar.id)


async def get_receivable(
    db: AsyncSession, clinic_id: UUID, ar_id: UUID,
) -> ARResponse:
    result = await db.execute(
        select(AccountReceivable)
        .where(AccountReceivable.id == ar_id, AccountReceivable.clinic_id == clinic_id)
        .options(
            selectinload(AccountReceivable.patient),
            selectinload(AccountReceivable.payments),
        )
    )
    ar = result.scalar_one_or_none()
    if not ar:
        raise NotFoundException("Cuenta por cobrar")
    return _ar_to_response(ar)


async def list_receivables(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID | None = None,
    status: AccountStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> ARListResponse:
    query = select(AccountReceivable).where(AccountReceivable.clinic_id == clinic_id)
    if patient_id:
        query = query.where(AccountReceivable.patient_id == patient_id)
    if status:
        query = query.where(AccountReceivable.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    query = (
        query
        .options(
            selectinload(AccountReceivable.patient),
            selectinload(AccountReceivable.payments),
        )
        .order_by(AccountReceivable.created_at.desc())
        .offset((page - 1) * size).limit(size)
    )
    result = await db.execute(query)
    items = result.scalars().unique().all()

    return ARListResponse(
        items=[_ar_to_response(a) for a in items],
        total=total, page=page, size=size, pages=pages,
    )


async def pay_receivable(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    ar_id: UUID,
    data: AccountPaymentCreate,
) -> ARResponse:
    """Registra un pago parcial/total en cuenta por cobrar."""
    result = await db.execute(
        select(AccountReceivable).where(
            AccountReceivable.id == ar_id,
            AccountReceivable.clinic_id == clinic_id,
        )
    )
    ar = result.scalar_one_or_none()
    if not ar:
        raise NotFoundException("Cuenta por cobrar")
    if ar.status == AccountStatus.PAID:
        raise ValidationException("Esta cuenta ya está pagada")

    amount = Decimal(str(data.amount))
    if amount > ar.balance:
        raise ValidationException(
            f"El monto ({data.amount}) excede el balance ({float(ar.balance)})"
        )

    payment = ARPayment(
        receivable_id=ar.id,
        amount=amount,
        payment_method=data.payment_method,
        cash_movement_id=data.cash_movement_id,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(payment)
    ar.amount_paid += amount
    _update_status(ar)

    await db.commit()
    return await get_receivable(db, clinic_id, ar.id)


# ── Account Payable ─────────────────────


async def create_payable(
    db: AsyncSession,
    clinic_id: UUID,
    data: APCreate,
) -> APResponse:
    """Crea una cuenta por pagar."""
    ap = AccountPayable(
        clinic_id=clinic_id,
        supplier_id=data.supplier_id,
        description=data.description,
        total_amount=Decimal(str(data.total_amount)),
        amount_paid=Decimal("0.00"),
        due_date=data.due_date,
        reference=data.reference,
        status=AccountStatus.PENDING,
    )
    db.add(ap)
    await db.commit()
    return await get_payable(db, clinic_id, ap.id)


async def get_payable(
    db: AsyncSession, clinic_id: UUID, ap_id: UUID,
) -> APResponse:
    result = await db.execute(
        select(AccountPayable)
        .where(AccountPayable.id == ap_id, AccountPayable.clinic_id == clinic_id)
        .options(
            selectinload(AccountPayable.supplier),
            selectinload(AccountPayable.payments),
        )
    )
    ap = result.scalar_one_or_none()
    if not ap:
        raise NotFoundException("Cuenta por pagar")
    return _ap_to_response(ap)


async def list_payables(
    db: AsyncSession,
    clinic_id: UUID,
    status: AccountStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> APListResponse:
    query = select(AccountPayable).where(AccountPayable.clinic_id == clinic_id)
    if status:
        query = query.where(AccountPayable.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    query = (
        query
        .options(
            selectinload(AccountPayable.supplier),
            selectinload(AccountPayable.payments),
        )
        .order_by(AccountPayable.created_at.desc())
        .offset((page - 1) * size).limit(size)
    )
    result = await db.execute(query)
    items = result.scalars().unique().all()

    return APListResponse(
        items=[_ap_to_response(a) for a in items],
        total=total, page=page, size=size, pages=pages,
    )


async def pay_payable(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    ap_id: UUID,
    data: AccountPaymentCreate,
) -> APResponse:
    """Registra un pago parcial/total en cuenta por pagar."""
    result = await db.execute(
        select(AccountPayable).where(
            AccountPayable.id == ap_id,
            AccountPayable.clinic_id == clinic_id,
        )
    )
    ap = result.scalar_one_or_none()
    if not ap:
        raise NotFoundException("Cuenta por pagar")
    if ap.status == AccountStatus.PAID:
        raise ValidationException("Esta cuenta ya está pagada")

    amount = Decimal(str(data.amount))
    if amount > ap.balance:
        raise ValidationException(
            f"El monto ({data.amount}) excede el balance ({float(ap.balance)})"
        )

    payment = APPayment(
        payable_id=ap.id,
        amount=amount,
        payment_method=data.payment_method,
        cash_movement_id=data.cash_movement_id,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(payment)
    ap.amount_paid += amount
    _update_status(ap)

    await db.commit()
    return await get_payable(db, clinic_id, ap.id)
