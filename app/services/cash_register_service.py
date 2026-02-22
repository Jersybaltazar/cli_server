"""
Lógica de negocio para el módulo de Caja.
Gestión de sesiones de caja y movimientos de ingreso/egreso.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.cash_register import (
    CashMovement,
    CashSession,
    CashSessionStatus,
    MovementCategory,
    MovementType,
    PaymentMethod,
)
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


# ── Helpers ───────────────────────────────────────────


async def _compute_session_totals(
    db: AsyncSession, session_id: UUID
) -> tuple[Decimal, Decimal]:
    """Calcula total de ingresos y egresos de una sesión."""
    income_result = await db.execute(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.session_id == session_id,
            CashMovement.movement_type == MovementType.INCOME,
        )
    )
    total_income = Decimal(str(income_result.scalar()))

    expense_result = await db.execute(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.session_id == session_id,
            CashMovement.movement_type == MovementType.EXPENSE,
        )
    )
    total_expense = Decimal(str(expense_result.scalar()))

    return total_income, total_expense


def _session_to_response(
    session: CashSession,
    total_income: Decimal = Decimal("0"),
    total_expense: Decimal = Decimal("0"),
) -> CashSessionResponse:
    """Convierte un modelo CashSession a su schema de respuesta."""
    return CashSessionResponse(
        id=session.id,
        clinic_id=session.clinic_id,
        opened_by=session.opened_by,
        closed_by=session.closed_by,
        status=session.status,
        opening_amount=session.opening_amount,
        expected_closing_amount=session.expected_closing_amount,
        actual_closing_amount=session.actual_closing_amount,
        difference=session.difference,
        total_income=total_income,
        total_expense=total_expense,
        notes=session.notes,
        opened_at=session.opened_at,
        closed_at=session.closed_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


# ── Session operations ────────────────────────────────


async def get_open_session(
    db: AsyncSession, clinic_id: UUID
) -> CashSessionResponse | None:
    """Retorna la sesión de caja abierta de la clínica, o None."""
    result = await db.execute(
        select(CashSession).where(
            CashSession.clinic_id == clinic_id,
            CashSession.status == CashSessionStatus.OPEN,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    total_income, total_expense = await _compute_session_totals(db, session.id)
    return _session_to_response(session, total_income, total_expense)


async def open_session(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    data: CashSessionOpen,
) -> CashSessionResponse:
    """Abre una nueva sesión de caja."""
    # Validar: no hay otra sesión abierta
    existing = await db.execute(
        select(CashSession).where(
            CashSession.clinic_id == clinic_id,
            CashSession.status == CashSessionStatus.OPEN,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException("Ya existe una caja abierta. Ciérrala antes de abrir otra.")

    session = CashSession(
        clinic_id=clinic_id,
        opened_by=user_id,
        opening_amount=data.opening_amount,
        notes=data.notes,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return _session_to_response(session)


async def close_session(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    session_id: UUID,
    data: CashSessionClose,
) -> CashSessionResponse:
    """Cierra una sesión de caja con cuadre de montos."""
    result = await db.execute(
        select(CashSession).where(
            CashSession.id == session_id,
            CashSession.clinic_id == clinic_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundException("Sesión de caja no encontrada")
    if session.status == CashSessionStatus.CLOSED:
        raise ConflictException("Esta caja ya fue cerrada")

    # Calcular montos esperados
    total_income, total_expense = await _compute_session_totals(db, session.id)
    expected = session.opening_amount + total_income - total_expense
    difference = data.actual_closing_amount - expected

    session.status = CashSessionStatus.CLOSED
    session.closed_by = user_id
    session.expected_closing_amount = expected
    session.actual_closing_amount = data.actual_closing_amount
    session.difference = difference
    session.closed_at = func.now()
    if data.notes:
        session.notes = (session.notes or "") + ("\n" + data.notes if session.notes else data.notes)

    await db.flush()
    await db.refresh(session)

    return _session_to_response(session, total_income, total_expense)


async def list_sessions(
    db: AsyncSession,
    clinic_id: UUID,
    page: int = 1,
    size: int = 20,
    status: CashSessionStatus | None = None,
) -> CashSessionListResponse:
    """Lista sesiones de caja con paginación."""
    query = select(CashSession).where(CashSession.clinic_id == clinic_id)
    count_query = select(func.count()).select_from(CashSession).where(
        CashSession.clinic_id == clinic_id
    )

    if status:
        query = query.where(CashSession.status == status)
        count_query = count_query.where(CashSession.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(CashSession.opened_at.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    sessions = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 1

    items = []
    for s in sessions:
        ti, te = await _compute_session_totals(db, s.id)
        items.append(_session_to_response(s, ti, te))

    return CashSessionListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ── Movement operations ──────────────────────────────


async def create_movement(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    data: CashMovementCreate,
) -> CashMovementResponse:
    """Registra un movimiento en la caja abierta."""
    # Obtener sesión abierta
    result = await db.execute(
        select(CashSession).where(
            CashSession.clinic_id == clinic_id,
            CashSession.status == CashSessionStatus.OPEN,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValidationException("No hay caja abierta. Abre una caja antes de registrar movimientos.")

    # Validar categoría vs tipo
    income_categories = {MovementCategory.PATIENT_PAYMENT, MovementCategory.OTHER_INCOME}
    if data.movement_type == MovementType.INCOME and data.category not in income_categories:
        raise ValidationException("Categoría inválida para un ingreso")
    if data.movement_type == MovementType.EXPENSE and data.category in income_categories:
        raise ValidationException("Categoría inválida para un egreso")

    movement = CashMovement(
        clinic_id=clinic_id,
        session_id=session.id,
        created_by=user_id,
        movement_type=data.movement_type,
        category=data.category,
        payment_method=data.payment_method,
        amount=data.amount,
        description=data.description,
        reference=data.reference,
        invoice_id=data.invoice_id,
        patient_id=data.patient_id,
        notes=data.notes,
    )
    db.add(movement)
    await db.flush()
    await db.refresh(movement)

    return CashMovementResponse.model_validate(movement)


async def list_movements(
    db: AsyncSession,
    clinic_id: UUID,
    session_id: UUID | None = None,
    page: int = 1,
    size: int = 50,
    movement_type: MovementType | None = None,
    category: MovementCategory | None = None,
) -> CashMovementListResponse:
    """Lista movimientos con filtros opcionales."""
    query = select(CashMovement).where(CashMovement.clinic_id == clinic_id)
    count_query = select(func.count()).select_from(CashMovement).where(
        CashMovement.clinic_id == clinic_id
    )

    if session_id:
        query = query.where(CashMovement.session_id == session_id)
        count_query = count_query.where(CashMovement.session_id == session_id)
    if movement_type:
        query = query.where(CashMovement.movement_type == movement_type)
        count_query = count_query.where(CashMovement.movement_type == movement_type)
    if category:
        query = query.where(CashMovement.category == category)
        count_query = count_query.where(CashMovement.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(CashMovement.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    movements = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 1

    return CashMovementListResponse(
        items=[CashMovementResponse.model_validate(m) for m in movements],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


async def get_daily_summary(
    db: AsyncSession, clinic_id: UUID, session_id: UUID
) -> DailyCashSummary:
    """Calcula el resumen agregado de una sesión de caja."""
    result = await db.execute(
        select(CashSession).where(
            CashSession.id == session_id,
            CashSession.clinic_id == clinic_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundException("Sesión de caja no encontrada")

    total_income, total_expense = await _compute_session_totals(db, session_id)
    balance = session.opening_amount + total_income - total_expense

    # Ingresos agrupados por método de pago
    income_by_method_result = await db.execute(
        select(
            CashMovement.payment_method,
            func.coalesce(func.sum(CashMovement.amount), 0),
        )
        .where(
            CashMovement.session_id == session_id,
            CashMovement.movement_type == MovementType.INCOME,
        )
        .group_by(CashMovement.payment_method)
    )
    income_by_method = {
        row[0].value: Decimal(str(row[1])) for row in income_by_method_result.all()
    }

    # Egresos agrupados por categoría
    expense_by_cat_result = await db.execute(
        select(
            CashMovement.category,
            func.coalesce(func.sum(CashMovement.amount), 0),
        )
        .where(
            CashMovement.session_id == session_id,
            CashMovement.movement_type == MovementType.EXPENSE,
        )
        .group_by(CashMovement.category)
    )
    expense_by_category = {
        row[0].value: Decimal(str(row[1])) for row in expense_by_cat_result.all()
    }

    # Conteo de movimientos
    count_result = await db.execute(
        select(func.count()).select_from(CashMovement).where(
            CashMovement.session_id == session_id
        )
    )
    movement_count = count_result.scalar() or 0

    return DailyCashSummary(
        session_id=session.id,
        status=session.status.value,
        opening_amount=session.opening_amount,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        income_by_method=income_by_method,
        expense_by_category=expense_by_category,
        movement_count=movement_count,
    )
