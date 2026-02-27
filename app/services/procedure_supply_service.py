"""
Servicio de ProcedureSupply — CRUD y auto-descuento de inventario.
"""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, ConflictException
from app.models.procedure_supply import ProcedureSupply
from app.models.logistica import InventoryItem, StockMovement, StockMovementType, StockMovementReason
from app.models.service import Service
from app.schemas.procedure_supply import (
    ProcedureSupplyCreate,
    ProcedureSupplyUpdate,
    ProcedureSupplyWithNames,
)

logger = logging.getLogger(__name__)


async def create_procedure_supply(
    db: AsyncSession,
    clinic_id: UUID,
    data: ProcedureSupplyCreate,
) -> ProcedureSupply:
    """Crea un mapeo servicio → insumo."""
    ps = ProcedureSupply(
        clinic_id=clinic_id,
        service_id=data.service_id,
        item_id=data.item_id,
        quantity=data.quantity,
    )
    db.add(ps)
    await db.commit()
    await db.refresh(ps)
    return ps


async def list_procedure_supplies(
    db: AsyncSession,
    clinic_id: UUID,
    service_id: UUID | None = None,
) -> list[ProcedureSupplyWithNames]:
    """Lista mapeos con nombres enriquecidos."""
    query = (
        select(ProcedureSupply, Service.name, InventoryItem.name, InventoryItem.code, InventoryItem.unit)
        .join(Service, ProcedureSupply.service_id == Service.id)
        .join(InventoryItem, ProcedureSupply.item_id == InventoryItem.id)
        .where(ProcedureSupply.clinic_id == clinic_id)
    )
    if service_id:
        query = query.where(ProcedureSupply.service_id == service_id)

    query = query.order_by(Service.name, InventoryItem.name)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for ps, svc_name, item_name, item_code, item_unit in rows:
        items.append(ProcedureSupplyWithNames(
            id=ps.id,
            clinic_id=ps.clinic_id,
            service_id=ps.service_id,
            item_id=ps.item_id,
            quantity=ps.quantity,
            is_active=ps.is_active,
            created_at=ps.created_at,
            updated_at=ps.updated_at,
            service_name=svc_name,
            item_name=item_name,
            item_code=item_code,
            item_unit=item_unit.value if item_unit else None,
        ))
    return items


async def update_procedure_supply(
    db: AsyncSession,
    clinic_id: UUID,
    ps_id: UUID,
    data: ProcedureSupplyUpdate,
) -> ProcedureSupply:
    """Actualiza cantidad o estado de un mapeo."""
    result = await db.execute(
        select(ProcedureSupply).where(
            ProcedureSupply.id == ps_id,
            ProcedureSupply.clinic_id == clinic_id,
        )
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise NotFoundException("Mapeo procedimiento-insumo no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ps, key, value)

    await db.commit()
    await db.refresh(ps)
    return ps


async def delete_procedure_supply(
    db: AsyncSession,
    clinic_id: UUID,
    ps_id: UUID,
) -> None:
    """Elimina un mapeo (hard delete)."""
    result = await db.execute(
        select(ProcedureSupply).where(
            ProcedureSupply.id == ps_id,
            ProcedureSupply.clinic_id == clinic_id,
        )
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise NotFoundException("Mapeo procedimiento-insumo no encontrado")

    await db.delete(ps)
    await db.commit()


async def auto_deduct_supplies(
    db: AsyncSession,
    clinic_id: UUID,
    service_id: UUID,
    appointment_id: UUID,
    user_id: UUID,
) -> list[StockMovement]:
    """
    Auto-descuenta insumos del inventario al completar una cita.
    Crea StockMovement EXIT por cada insumo vinculado al servicio.

    Returns:
        Lista de movimientos de stock creados.
    """
    # Buscar mapeos activos para este servicio
    result = await db.execute(
        select(ProcedureSupply).where(
            ProcedureSupply.clinic_id == clinic_id,
            ProcedureSupply.service_id == service_id,
            ProcedureSupply.is_active.is_(True),
        )
    )
    supplies = result.scalars().all()

    if not supplies:
        return []

    movements = []
    for ps in supplies:
        # Obtener item de inventario
        item_result = await db.execute(
            select(InventoryItem).where(InventoryItem.id == ps.item_id)
        )
        item = item_result.scalar_one_or_none()
        if not item:
            logger.warning(f"InventoryItem {ps.item_id} no encontrado, skip")
            continue

        stock_before = item.current_stock
        stock_after = stock_before - ps.quantity

        # Crear movimiento de salida
        movement = StockMovement(
            clinic_id=clinic_id,
            item_id=item.id,
            created_by=user_id,
            movement_type=StockMovementType.EXIT,
            reason=StockMovementReason.PATIENT_USE,
            quantity=ps.quantity,
            unit_cost=item.unit_cost,
            total_cost=ps.quantity * item.unit_cost,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=f"appointment:{appointment_id}",
        )
        db.add(movement)

        # Actualizar stock
        item.current_stock = stock_after
        movements.append(movement)

        if stock_after < item.min_stock:
            logger.warning(
                f"Stock bajo para {item.name} [{item.code}]: "
                f"{stock_after} < min {item.min_stock}"
            )

    await db.flush()
    return movements
