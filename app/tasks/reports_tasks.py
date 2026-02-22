"""
Tareas Celery para generación asíncrona de reportes.
Útil para reportes pesados que toman tiempo.
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="reports.generate_monthly_summary")
def generate_monthly_summary_task(clinic_id: str, year: int, month: int):
    """
    Genera un resumen mensual de la clínica.
    Se puede programar con Celery Beat el 1er día de cada mes.
    """
    from datetime import date
    from uuid import UUID

    async def _generate():
        from app.database import async_session_factory
        from app.services.report_service import (
            get_appointment_stats,
            get_revenue_report,
        )

        date_from = date(year, month, 1)
        if month == 12:
            date_to = date(year + 1, 1, 1)
        else:
            date_to = date(year, month + 1, 1)
        # Último día del mes
        from datetime import timedelta
        date_to = date_to - timedelta(days=1)

        async with async_session_factory() as db:
            revenue = await get_revenue_report(
                db, UUID(clinic_id), date_from, date_to
            )
            stats = await get_appointment_stats(
                db, UUID(clinic_id), date_from, date_to
            )

            logger.info(
                f"Resumen {year}-{month:02d} clínica {clinic_id}: "
                f"Ingresos S/{revenue.grand_total}, "
                f"Citas: {stats.total}, "
                f"No-show: {stats.no_show_rate}%"
            )

            # Aquí se podría guardar en una tabla de reportes
            # o enviar por email al administrador
            return {
                "clinic_id": clinic_id,
                "period": f"{year}-{month:02d}",
                "revenue": str(revenue.grand_total),
                "appointments": stats.total,
                "no_show_rate": stats.no_show_rate,
            }

    return asyncio.run(_generate())
