"""
Tareas Celery para sincronización offline.
Procesamiento de colas pesadas y mantenimiento de datos de sync.
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="sync.process_batch",
)
def process_sync_batch_task(
    self,
    queue_entry_id: str,
    user_id: str,
    clinic_id: str,
):
    """
    Task asíncrono para procesar un batch de sync pesado en background.
    Se usa cuando el batch tiene más de un umbral de operaciones
    para no bloquear el endpoint HTTP.
    """
    from uuid import UUID

    async def _process():
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.database import async_session_factory
        from app.models.sync_queue import SyncQueue, SyncStatus
        from app.models.user import User
        from app.schemas.sync import SyncBatch, SyncOperation
        from app.services.sync_service import _process_operation, _get_server_updates

        async with async_session_factory() as db:
            # Cargar el batch de la cola
            result = await db.execute(
                select(SyncQueue).where(SyncQueue.id == UUID(queue_entry_id))
            )
            queue_entry = result.scalar_one_or_none()

            if not queue_entry:
                logger.error(f"SyncQueue {queue_entry_id} no encontrado")
                return

            if queue_entry.status != SyncStatus.PENDING:
                logger.info(
                    f"SyncQueue {queue_entry_id} ya está en estado "
                    f"{queue_entry.status.value}, omitiendo"
                )
                return

            # Cargar usuario
            user_result = await db.execute(
                select(User).where(User.id == UUID(user_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                queue_entry.status = SyncStatus.FAILED
                queue_entry.error_message = f"Usuario {user_id} no encontrado"
                await db.commit()
                return

            # Marcar como procesando
            queue_entry.status = SyncStatus.PROCESSING
            await db.flush()

            # Reconstruir operaciones desde el JSONB
            operations_data = queue_entry.operations.get("operations", [])
            applied_count = 0
            conflict_count = 0
            error_count = 0

            for op_data in operations_data:
                try:
                    op = SyncOperation(**op_data)
                    from app.schemas.sync import SyncApplied, SyncConflict
                    result = await _process_operation(
                        db,
                        UUID(clinic_id),
                        user,
                        queue_entry.device_id,
                        op,
                    )
                    if isinstance(result, SyncApplied):
                        applied_count += 1
                    elif isinstance(result, SyncConflict):
                        conflict_count += 1
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error en operación: {e}")

            # Actualizar estado final
            from datetime import datetime, timezone

            queue_entry.processed_at = datetime.now(timezone.utc)
            queue_entry.result = {
                "applied_count": applied_count,
                "conflicts_count": conflict_count,
                "errors_count": error_count,
            }

            if error_count > 0 and applied_count == 0:
                queue_entry.status = SyncStatus.FAILED
                queue_entry.error_message = f"{error_count} operaciones fallaron"
            elif error_count > 0:
                queue_entry.status = SyncStatus.PARTIAL
                queue_entry.error_message = f"{error_count} de {len(operations_data)} fallaron"
            else:
                queue_entry.status = SyncStatus.COMPLETED

            await db.commit()

            logger.info(
                f"Batch {queue_entry_id} procesado: "
                f"{applied_count} aplicadas, {conflict_count} conflictos, "
                f"{error_count} errores"
            )

    try:
        asyncio.run(_process())
    except Exception as exc:
        logger.error(f"Error procesando batch {queue_entry_id}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="sync.process_pending_batches")
def process_pending_batches():
    """
    Task periódico: procesa batches de sincronización que quedaron
    en estado PENDING (por ejemplo, si el worker se cayó).
    Ejecutar como cron cada 5 minutos.
    """
    async def _process():
        from sqlalchemy import select

        from app.database import async_session_factory
        from app.models.sync_queue import SyncQueue, SyncStatus

        async with async_session_factory() as db:
            result = await db.execute(
                select(SyncQueue.id, SyncQueue.user_id, SyncQueue.clinic_id).where(
                    SyncQueue.status == SyncStatus.PENDING,
                ).limit(20)
            )
            pending = result.all()

        for entry_id, uid, cid in pending:
            process_sync_batch_task.delay(
                str(entry_id), str(uid), str(cid)
            )

        if pending:
            logger.info(f"Encolados {len(pending)} batches pendientes de sync")

    asyncio.run(_process())


@celery_app.task(name="sync.cleanup_old_data")
def cleanup_old_sync_data(days_to_keep: int = 90):
    """
    Task periódico: limpia datos de sincronización antiguos.
    - Borra batches completados de más de N días
    - Borra mapeos huérfanos
    Ejecutar como cron semanal.
    """
    async def _cleanup():
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete

        from app.database import async_session_factory
        from app.models.sync_queue import SyncDeviceMapping, SyncQueue, SyncStatus

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        async with async_session_factory() as db:
            # Eliminar batches completados antiguos
            result = await db.execute(
                delete(SyncQueue).where(
                    SyncQueue.status.in_([SyncStatus.COMPLETED, SyncStatus.PARTIAL]),
                    SyncQueue.processed_at < cutoff,
                )
            )
            deleted_batches = result.rowcount

            # Eliminar mapeos antiguos
            mapping_result = await db.execute(
                delete(SyncDeviceMapping).where(
                    SyncDeviceMapping.created_at < cutoff,
                )
            )
            deleted_mappings = mapping_result.rowcount

            await db.commit()

            logger.info(
                f"Limpieza sync: {deleted_batches} batches y "
                f"{deleted_mappings} mapeos eliminados (>{days_to_keep} días)"
            )

    asyncio.run(_cleanup())
