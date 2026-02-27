"""
Lógica de negocio para comisiones médicas.
CRUD de reglas, generación automática de entries, liquidación y pago.
"""

import math
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.commission import (
    CommissionEntry,
    CommissionEntryStatus,
    CommissionRule,
    CommissionType,
)
from app.models.service import Service
from app.models.user import User
from app.models.patient import Patient
from app.schemas.commission import (
    CommissionEntryListResponse,
    CommissionEntryResponse,
    CommissionMarkPaid,
    CommissionRuleCreate,
    CommissionRuleResponse,
    CommissionRuleUpdate,
    DoctorLiquidation,
    LiquidationResponse,
)


# ── Helpers ──────────────────────────────


def _rule_to_response(rule: CommissionRule) -> CommissionRuleResponse:
    return CommissionRuleResponse(
        id=rule.id,
        clinic_id=rule.clinic_id,
        doctor_id=rule.doctor_id,
        service_id=rule.service_id,
        commission_type=rule.commission_type,
        value=float(rule.value),
        is_active=rule.is_active,
        service_name=rule.service.name if rule.service else None,
        doctor_name=(
            f"{rule.doctor.first_name} {rule.doctor.last_name}"
            if rule.doctor else None
        ),
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _entry_to_response(entry: CommissionEntry) -> CommissionEntryResponse:
    return CommissionEntryResponse(
        id=entry.id,
        clinic_id=entry.clinic_id,
        doctor_id=entry.doctor_id,
        appointment_id=entry.appointment_id,
        service_id=entry.service_id,
        patient_id=entry.patient_id,
        service_amount=float(entry.service_amount),
        commission_amount=float(entry.commission_amount),
        status=entry.status,
        period=entry.period,
        paid_at=entry.paid_at,
        paid_reference=entry.paid_reference,
        created_at=entry.created_at,
        doctor_name=(
            f"{entry.doctor.first_name} {entry.doctor.last_name}"
            if entry.doctor else None
        ),
        service_name=entry.service.name if entry.service else None,
        patient_name=entry.patient.full_name if entry.patient else None,
    )


# ── CRUD Rules ───────────────────────────


async def create_rule(
    db: AsyncSession,
    clinic_id: UUID,
    data: CommissionRuleCreate,
) -> CommissionRuleResponse:
    """Crea una regla de comisión."""
    # Verificar unicidad
    existing = await db.execute(
        select(CommissionRule).where(
            CommissionRule.clinic_id == clinic_id,
            CommissionRule.doctor_id == data.doctor_id,
            CommissionRule.service_id == data.service_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(
            "Ya existe una regla de comisión para este doctor y servicio"
        )

    rule = CommissionRule(
        clinic_id=clinic_id,
        doctor_id=data.doctor_id,
        service_id=data.service_id,
        commission_type=data.commission_type,
        value=Decimal(str(data.value)),
        is_active=data.is_active,
    )
    db.add(rule)
    await db.commit()

    # Recargar con relaciones
    result = await db.execute(
        select(CommissionRule)
        .where(CommissionRule.id == rule.id)
        .options(
            selectinload(CommissionRule.service),
            selectinload(CommissionRule.doctor),
        )
    )
    return _rule_to_response(result.scalar_one())


async def list_rules(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID | None = None,
    service_id: UUID | None = None,
    is_active: bool | None = None,
) -> list[CommissionRuleResponse]:
    """Lista reglas de comisión."""
    query = (
        select(CommissionRule)
        .where(CommissionRule.clinic_id == clinic_id)
        .options(
            selectinload(CommissionRule.service),
            selectinload(CommissionRule.doctor),
        )
    )
    if doctor_id:
        query = query.where(CommissionRule.doctor_id == doctor_id)
    if service_id:
        query = query.where(CommissionRule.service_id == service_id)
    if is_active is not None:
        query = query.where(CommissionRule.is_active == is_active)

    result = await db.execute(query.order_by(CommissionRule.created_at))
    return [_rule_to_response(r) for r in result.scalars().all()]


async def update_rule(
    db: AsyncSession,
    clinic_id: UUID,
    rule_id: UUID,
    data: CommissionRuleUpdate,
) -> CommissionRuleResponse:
    """Actualiza una regla de comisión."""
    result = await db.execute(
        select(CommissionRule).where(
            CommissionRule.id == rule_id,
            CommissionRule.clinic_id == clinic_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundException("Regla de comisión")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "value" and value is not None:
            value = Decimal(str(value))
        setattr(rule, key, value)

    await db.commit()

    result = await db.execute(
        select(CommissionRule)
        .where(CommissionRule.id == rule.id)
        .options(
            selectinload(CommissionRule.service),
            selectinload(CommissionRule.doctor),
        )
    )
    return _rule_to_response(result.scalar_one())


async def delete_rule(
    db: AsyncSession,
    clinic_id: UUID,
    rule_id: UUID,
) -> None:
    """Desactiva una regla de comisión."""
    result = await db.execute(
        select(CommissionRule).where(
            CommissionRule.id == rule_id,
            CommissionRule.clinic_id == clinic_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundException("Regla de comisión")

    rule.is_active = False
    await db.commit()


# ── Auto-generación de comisión ──────────


async def generate_commission_entry(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID,
    appointment_id: UUID,
    service_id: UUID,
    patient_id: UUID,
    service_amount: Decimal,
) -> None:
    """
    Genera una entrada de comisión al completar una cita.
    Busca primero regla específica del doctor, luego regla default (doctor_id=null).
    Si no hay regla, no genera comisión.
    """
    # Buscar regla específica para este doctor + servicio
    result = await db.execute(
        select(CommissionRule).where(
            CommissionRule.clinic_id == clinic_id,
            CommissionRule.doctor_id == doctor_id,
            CommissionRule.service_id == service_id,
            CommissionRule.is_active.is_(True),
        )
    )
    rule = result.scalar_one_or_none()

    # Si no hay específica, buscar default (doctor_id is null)
    if not rule:
        result = await db.execute(
            select(CommissionRule).where(
                CommissionRule.clinic_id == clinic_id,
                CommissionRule.doctor_id.is_(None),
                CommissionRule.service_id == service_id,
                CommissionRule.is_active.is_(True),
            )
        )
        rule = result.scalar_one_or_none()

    if not rule:
        return  # Sin regla, no se genera comisión

    # Calcular monto
    if rule.commission_type == CommissionType.PERCENTAGE:
        commission_amount = service_amount * rule.value / Decimal("100")
    else:
        commission_amount = rule.value

    now = datetime.now(timezone.utc)
    period = now.strftime("%Y-%m")

    entry = CommissionEntry(
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        appointment_id=appointment_id,
        service_id=service_id,
        patient_id=patient_id,
        service_amount=service_amount,
        commission_amount=commission_amount,
        status=CommissionEntryStatus.PENDING,
        period=period,
    )
    db.add(entry)


# ── Listado de entries ───────────────────


async def list_entries(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID | None = None,
    period: str | None = None,
    status: CommissionEntryStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> CommissionEntryListResponse:
    """Lista entradas de comisión con filtros."""
    query = select(CommissionEntry).where(CommissionEntry.clinic_id == clinic_id)

    if doctor_id:
        query = query.where(CommissionEntry.doctor_id == doctor_id)
    if period:
        query = query.where(CommissionEntry.period == period)
    if status:
        query = query.where(CommissionEntry.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    query = (
        query
        .options(
            selectinload(CommissionEntry.doctor),
            selectinload(CommissionEntry.service),
            selectinload(CommissionEntry.patient),
        )
        .order_by(CommissionEntry.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    entries = result.scalars().unique().all()

    return CommissionEntryListResponse(
        items=[_entry_to_response(e) for e in entries],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ── Liquidación por período ──────────────


async def get_liquidation(
    db: AsyncSession,
    clinic_id: UUID,
    period: str,
    doctor_id: UUID | None = None,
) -> LiquidationResponse:
    """Resumen de comisiones por doctor para un período."""
    query = (
        select(
            CommissionEntry.doctor_id,
            func.count(CommissionEntry.id).label("total_services"),
            func.sum(CommissionEntry.service_amount).label("total_service_amount"),
            func.sum(CommissionEntry.commission_amount).label("total_commission"),
            func.sum(
                case(
                    (CommissionEntry.status == CommissionEntryStatus.PENDING,
                     CommissionEntry.commission_amount),
                    else_=Decimal("0"),
                )
            ).label("pending_amount"),
            func.sum(
                case(
                    (CommissionEntry.status == CommissionEntryStatus.PAID,
                     CommissionEntry.commission_amount),
                    else_=Decimal("0"),
                )
            ).label("paid_amount"),
        )
        .where(
            CommissionEntry.clinic_id == clinic_id,
            CommissionEntry.period == period,
        )
        .group_by(CommissionEntry.doctor_id)
    )

    if doctor_id:
        query = query.where(CommissionEntry.doctor_id == doctor_id)

    result = await db.execute(query)
    rows = result.all()

    doctors = []
    grand_total = Decimal("0")
    grand_pending = Decimal("0")
    grand_paid = Decimal("0")

    for row in rows:
        # Obtener nombre del doctor
        doc_result = await db.execute(
            select(User.first_name, User.last_name).where(User.id == row.doctor_id)
        )
        doc = doc_result.one_or_none()
        doctor_name = f"{doc.first_name} {doc.last_name}" if doc else "Desconocido"

        total_commission = Decimal(str(row.total_commission or 0))
        pending = Decimal(str(row.pending_amount or 0))
        paid = Decimal(str(row.paid_amount or 0))

        # Cargar entries individuales del doctor para este período
        entries_result = await db.execute(
            select(CommissionEntry)
            .where(
                CommissionEntry.clinic_id == clinic_id,
                CommissionEntry.doctor_id == row.doctor_id,
                CommissionEntry.period == period,
            )
            .options(
                selectinload(CommissionEntry.doctor),
                selectinload(CommissionEntry.service),
                selectinload(CommissionEntry.patient),
            )
            .order_by(CommissionEntry.created_at.desc())
        )
        entries = entries_result.scalars().all()

        doctors.append(DoctorLiquidation(
            doctor_id=row.doctor_id,
            doctor_name=doctor_name,
            total_services=row.total_services,
            total_service_amount=float(row.total_service_amount or 0),
            total_commission=float(total_commission),
            pending_amount=float(pending),
            paid_amount=float(paid),
            entries=[_entry_to_response(e) for e in entries],
        ))

        grand_total += total_commission
        grand_pending += pending
        grand_paid += paid

    return LiquidationResponse(
        period=period,
        clinic_id=clinic_id,
        doctors=doctors,
        grand_total_commission=float(grand_total),
        grand_total_pending=float(grand_pending),
        grand_total_paid=float(grand_paid),
    )


# ── Marcar como pagado ──────────────────


async def mark_as_paid(
    db: AsyncSession,
    clinic_id: UUID,
    data: CommissionMarkPaid,
) -> int:
    """Marca un lote de comisiones como pagadas. Retorna cantidad actualizada."""
    now = datetime.now(timezone.utc)
    count = 0

    for entry_id in data.entry_ids:
        result = await db.execute(
            select(CommissionEntry).where(
                CommissionEntry.id == entry_id,
                CommissionEntry.clinic_id == clinic_id,
                CommissionEntry.status == CommissionEntryStatus.PENDING,
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            entry.status = CommissionEntryStatus.PAID
            entry.paid_at = now
            entry.paid_reference = data.paid_reference
            count += 1

    await db.commit()
    return count
