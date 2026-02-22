"""
Endpoints de sincronización offline.

POST /sync          — Procesar un batch de operaciones offline
GET  /sync/status   — Estado de sincronización de un dispositivo
POST /sync/async    — Enviar batch grande para procesamiento async (Celery)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.sync_queue import SyncQueue, SyncStatus
from app.models.user import User
from app.schemas.sync import SyncBatch, SyncResponse, SyncStatusResponse
from app.services.sync_service import get_sync_status, process_sync_batch

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Umbral para procesamiento asíncrono ──────────────
ASYNC_THRESHOLD = 50  # operaciones


@router.post(
    "",
    response_model=SyncResponse,
    summary="Sincronizar operaciones offline",
    description=(
        "Recibe un batch de operaciones realizadas offline y las procesa. "
        "Si el batch tiene más de 50 operaciones, considerar usar /sync/async."
    ),
)
async def sync_batch(
    batch: SyncBatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncResponse:
    """
    Endpoint principal de sincronización.
    Procesa operaciones sincrónicas y retorna resultados inmediatos.
    """
    logger.info(
        f"Sync batch recibido: device={batch.device_id}, "
        f"operations={len(batch.operations)}, user={current_user.id}"
    )

    result = await process_sync_batch(db, current_user, batch)

    logger.info(
        f"Sync batch {result.batch_id} procesado: "
        f"applied={len(result.applied)}, "
        f"conflicts={len(result.conflicts)}, "
        f"errors={len(result.errors)}"
    )

    return result


@router.post(
    "/async",
    response_model=dict,
    summary="Enviar batch para procesamiento asíncrono",
    description=(
        "Para batches grandes (>50 operaciones). "
        "El batch se encola en Celery y se puede consultar el estado."
    ),
)
async def sync_batch_async(
    batch: SyncBatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Encola un batch de operaciones para procesamiento asíncrono.
    Retorna el batch_id para consultar el estado posteriormente.
    """
    from app.tasks.sync_tasks import process_sync_batch_task

    # Registrar el batch en la cola
    queue_entry = SyncQueue(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        device_id=batch.device_id,
        operations={"operations": [op.model_dump(mode="json") for op in batch.operations]},
        operation_count=len(batch.operations),
        status=SyncStatus.PENDING,
    )
    db.add(queue_entry)
    await db.flush()

    # Encolar en Celery
    process_sync_batch_task.delay(
        str(queue_entry.id),
        str(current_user.id),
        str(current_user.clinic_id),
    )

    logger.info(
        f"Batch {queue_entry.id} encolado para procesamiento async "
        f"({len(batch.operations)} operaciones)"
    )

    return {
        "batch_id": str(queue_entry.id),
        "status": "queued",
        "operation_count": len(batch.operations),
        "message": "Batch encolado para procesamiento. Consultar estado con GET /sync/status.",
    }


@router.get(
    "/status",
    response_model=SyncStatusResponse,
    summary="Estado de sincronización de un dispositivo",
    description="Retorna el estado actual de sincronización, último sync exitoso y batches pendientes.",
)
async def sync_status(
    device_id: str = Query(..., min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncStatusResponse:
    """Consulta el estado de sincronización de un dispositivo."""
    return await get_sync_status(
        db, current_user.clinic_id, device_id
    )


@router.get(
    "/batch/{batch_id}",
    response_model=dict,
    summary="Consultar estado de un batch específico",
    description="Retorna el estado y resultado de un batch de sincronización.",
)
async def get_batch_status(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Consulta el estado de un batch específico."""
    from uuid import UUID

    from sqlalchemy import select

    result = await db.execute(
        select(SyncQueue).where(
            SyncQueue.id == UUID(batch_id),
            SyncQueue.clinic_id == current_user.clinic_id,
        )
    )
    queue_entry = result.scalar_one_or_none()

    if not queue_entry:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("Batch de sincronización no encontrado")

    return {
        "batch_id": str(queue_entry.id),
        "status": queue_entry.status.value,
        "operation_count": queue_entry.operation_count,
        "result": queue_entry.result,
        "error_message": queue_entry.error_message,
        "created_at": queue_entry.created_at.isoformat() if queue_entry.created_at else None,
        "processed_at": queue_entry.processed_at.isoformat() if queue_entry.processed_at else None,
    }
