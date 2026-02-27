from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lab_order import LabOrder, LabOrderStatus, LabStudyType
from app.models.lab_result import LabResult
from app.models.lab_sequence import LabSequence
from app.models.user import User
from app.schemas.lab import LabOrderCreate, LabOrderUpdate, LabResultCreate, LabDashboardStats
from app.core.exceptions import NotFoundException, ConflictException


# ── Generación de códigos secuenciales ──────────────────

_SEQUENCE_MAP = {
    LabStudyType.PATHOLOGY: ("pathology", "M"),
    LabStudyType.CYTOLOGY: ("cytology", "C"),
}


async def _generate_lab_code(
    db: AsyncSession, clinic_id: UUID, study_type: LabStudyType
) -> str | None:
    """
    Genera código secuencial M26-01, C26-01 etc.
    Usa SELECT FOR UPDATE para evitar duplicados en concurrencia.
    Retorna None si el tipo de estudio no requiere código.
    """
    mapping = _SEQUENCE_MAP.get(study_type)
    if not mapping:
        return None

    seq_type, prefix = mapping
    year = datetime.now().year
    year_short = year % 100  # 2026 → 26

    # Buscar o crear secuencia con lock
    result = await db.execute(
        select(LabSequence)
        .where(
            LabSequence.clinic_id == clinic_id,
            LabSequence.sequence_type == seq_type,
            LabSequence.year == year,
        )
        .with_for_update()
    )
    seq = result.scalar_one_or_none()

    if not seq:
        seq = LabSequence(
            clinic_id=clinic_id,
            sequence_type=seq_type,
            year=year,
            last_number=0,
        )
        db.add(seq)
        await db.flush()

    seq.last_number += 1
    return f"{prefix}{year_short}-{seq.last_number:02d}"


async def create_order(
    db: AsyncSession,
    clinic_id: UUID,
    user_id: UUID,
    data: LabOrderCreate
) -> LabOrder:
    """Crea una nueva orden de laboratorio."""
    # Generar código secuencial si es patología o citología
    lab_code = await _generate_lab_code(db, clinic_id, data.study_type)

    order = LabOrder(
        **data.model_dump(exclude={"doctor_id"}),
        clinic_id=clinic_id,
        doctor_id=data.doctor_id or user_id,
        status=LabOrderStatus.ORDERED,
        ordered_at=func.now(),
        lab_code=lab_code,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order

async def get_order(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> LabOrder:
    """Obtiene una orden por ID con su resultado cargado."""
    result = await db.execute(
        select(LabOrder)
        .where(LabOrder.id == order_id, LabOrder.clinic_id == clinic_id)
        .options(selectinload(LabOrder.result))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundException("Orden de laboratorio no encontrada")
    return order

async def list_orders(
    db: AsyncSession,
    clinic_id: UUID,
    status: LabOrderStatus | None = None,
    study_type: LabStudyType | None = None,
    patient_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    size: int = 50
):
    """Lista órdenes con filtros y paginación."""
    query = select(LabOrder).where(LabOrder.clinic_id == clinic_id)
    
    if status:
        query = query.where(LabOrder.status == status)
    if study_type:
        query = query.where(LabOrder.study_type == study_type)
    if patient_id:
        query = query.where(LabOrder.patient_id == patient_id)
    if date_from:
        query = query.where(LabOrder.ordered_at >= date_from)
    if date_to:
        query = query.where(LabOrder.ordered_at <= date_to)

    # Contar totales para paginación
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Aplicar paginación y orden
    query = query.order_by(LabOrder.ordered_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query.options(selectinload(LabOrder.result)))
    items = result.scalars().all()

    # Contar pendientes y vencidos
    pending_query = select(func.count()).where(
        LabOrder.clinic_id == clinic_id,
        LabOrder.status.in_([LabOrderStatus.ORDERED, LabOrderStatus.SAMPLE_TAKEN, LabOrderStatus.SENT])
    )
    pending_count = (await db.execute(pending_query)).scalar_one()

    overdue_threshold = datetime.now() - timedelta(days=15)
    overdue_query = select(func.count()).where(
        LabOrder.clinic_id == clinic_id,
        LabOrder.status.in_([LabOrderStatus.ORDERED, LabOrderStatus.SAMPLE_TAKEN, LabOrderStatus.SENT]),
        LabOrder.ordered_at < overdue_threshold
    )
    overdue_count = (await db.execute(overdue_query)).scalar_one()

    return {
        "items": items,
        "total": total,
        "pending_count": pending_count,
        "overdue_count": overdue_count
    }

async def update_order(
    db: AsyncSession,
    clinic_id: UUID,
    order_id: UUID,
    data: LabOrderUpdate,
    user_id: UUID
) -> LabOrder:
    """Actualiza una orden (cambio de estado o datos de tracking)."""
    order = await get_order(db, clinic_id, order_id)
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Lógica especial para cambios de estado
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == LabOrderStatus.SAMPLE_TAKEN:
            order.sample_taken_at = update_data.get("sample_taken_at", func.now())
            order.sample_taken_by = update_data.get("sample_taken_by", user_id)
        elif new_status == LabOrderStatus.SENT:
            order.sent_at = update_data.get("sent_at", func.now())
        elif new_status == LabOrderStatus.RESULT_RECEIVED:
            order.result_received_at = update_data.get("result_received_at", func.now())
        elif new_status == LabOrderStatus.DELIVERED:
            order.delivered_at = update_data.get("delivered_at", func.now())
            if "delivered_by" not in update_data:
                order.delivered_by = user_id

    for key, value in update_data.items():
        setattr(order, key, value)

    await db.commit()
    await db.refresh(order)
    return order

async def register_result(
    db: AsyncSession,
    clinic_id: UUID,
    order_id: UUID,
    user_id: UUID,
    data: LabResultCreate
) -> LabResult:
    """Registra el resultado de una orden y actualiza su estado."""
    order = await get_order(db, clinic_id, order_id)
    
    if order.status == LabOrderStatus.CANCELLED:
        raise ConflictException("No se puede registrar resultado en una orden cancelada")

    # Crear el resultado (lab_order_id viene del path, no del body)
    result_obj = LabResult(
        **data.model_dump(exclude={"lab_order_id"}),
        lab_order_id=order_id,
        clinic_id=clinic_id,
        recorded_by=user_id,
        recorded_at=func.now()
    )
    db.add(result_obj)
    
    # Actualizar estado de la orden
    order.status = LabOrderStatus.RESULT_RECEIVED
    order.result_received_at = func.now()
    
    await db.commit()
    await db.refresh(result_obj)
    return result_obj

async def get_dashboard_stats(db: AsyncSession, clinic_id: UUID) -> LabDashboardStats:
    """Calcula estadísticas para el dashboard de laboratorio."""
    # Total de órdenes
    total = await db.scalar(select(func.count(LabOrder.id)).where(LabOrder.clinic_id == clinic_id))
    
    # Pendientes de muestra (ORDERED)
    pending_samples = await db.scalar(
        select(func.count(LabOrder.id)).where(
            LabOrder.clinic_id == clinic_id, LabOrder.status == LabOrderStatus.ORDERED
        )
    )
    
    # Enviados esperando resultado (SENT)
    sent_awaiting = await db.scalar(
        select(func.count(LabOrder.id)).where(
            LabOrder.clinic_id == clinic_id, LabOrder.status == LabOrderStatus.SENT
        )
    )
    
    # Resultados por entregar (RESULT_RECEIVED)
    to_deliver = await db.scalar(
        select(func.count(LabOrder.id)).where(
            LabOrder.clinic_id == clinic_id, LabOrder.status == LabOrderStatus.RESULT_RECEIVED
        )
    )
    
    # Vencidos (> 15 días sin resultado)
    overdue_threshold = datetime.now() - timedelta(days=15)
    overdue = await db.scalar(
        select(func.count(LabOrder.id)).where(
            LabOrder.clinic_id == clinic_id,
            LabOrder.status.in_([LabOrderStatus.ORDERED, LabOrderStatus.SAMPLE_TAKEN, LabOrderStatus.SENT]),
            LabOrder.ordered_at < overdue_threshold
        )
    )

    return LabDashboardStats(
        total_orders=total or 0,
        pending_samples=pending_samples or 0,
        sent_awaiting=sent_awaiting or 0,
        results_to_deliver=to_deliver or 0,
        overdue=overdue or 0
    )

async def get_patient_history(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[LabOrder]:
    """Obtiene el historial completo de laboratorio de un paciente."""
    result = await db.execute(
        select(LabOrder)
        .where(LabOrder.clinic_id == clinic_id, LabOrder.patient_id == patient_id)
        .order_by(LabOrder.ordered_at.desc())
        .options(selectinload(LabOrder.result))
    )
    return list(result.scalars().all())
