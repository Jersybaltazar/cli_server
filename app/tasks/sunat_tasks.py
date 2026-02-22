"""
Tareas Celery para facturación SUNAT.
Emisión asíncrona y reintentos automáticos.
Multi-tenant: cada clínica usa su propio token NubeFact.
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="sunat.emit_invoice",
)
def emit_invoice_task(self, invoice_id: str, clinic_id: str):
    """
    Task asíncrono para emitir un comprobante a SUNAT vía NubeFact.
    Se reintenta hasta 3 veces con 60s de espera.
    Obtiene el token NubeFact de la clínica correspondiente.
    """
    from uuid import UUID

    async def _emit():
        from app.database import async_session_factory
        from app.models.invoice import Invoice, SunatStatus
        from app.services.sunat_service import (
            NubefactError,
            build_nubefact_payload,
            emit_to_nubefact,
            get_clinic_nubefact_token,
            parse_nubefact_response,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        async with async_session_factory() as db:
            result = await db.execute(
                select(Invoice)
                .options(joinedload(Invoice.items))
                .where(Invoice.id == UUID(invoice_id))
            )
            invoice = result.scalar_one_or_none()

            if not invoice:
                logger.error(f"Invoice {invoice_id} no encontrado")
                return

            if invoice.sunat_status in (SunatStatus.ACCEPTED, SunatStatus.VOIDED):
                logger.info(f"Invoice {invoice_id} ya procesado ({invoice.sunat_status.value})")
                return

            try:
                # Obtener token de la clínica
                token = await get_clinic_nubefact_token(db, invoice.clinic_id)

                payload = build_nubefact_payload(invoice)
                response_data = await emit_to_nubefact(payload, token=token)
                status, error_msg = parse_nubefact_response(response_data)

                invoice.sunat_status = status
                invoice.nubefact_response = response_data
                invoice.sunat_error_message = error_msg
                invoice.pdf_url = response_data.get("enlace_del_pdf")
                invoice.xml_url = response_data.get("enlace_del_xml")
                invoice.cdr_url = response_data.get("enlace_del_cdr")

                await db.commit()
                logger.info(f"Invoice {invoice_id} emitido: {status.value}")

            except NubefactError as e:
                invoice.sunat_status = SunatStatus.ERROR
                invoice.sunat_error_message = e.message
                await db.commit()
                raise

    try:
        asyncio.run(_emit())
    except Exception as exc:
        logger.error(f"Error emitiendo invoice {invoice_id}: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="sunat.process_queued")
def process_queued_invoices():
    """
    Task periódico: procesa comprobantes en cola (estado QUEUED).
    Útil para cuando el sistema estaba offline y encoló emisiones.
    """
    async def _process():
        from app.database import async_session_factory
        from app.models.invoice import Invoice, SunatStatus
        from sqlalchemy import select

        async with async_session_factory() as db:
            result = await db.execute(
                select(Invoice.id, Invoice.clinic_id).where(
                    Invoice.sunat_status.in_([SunatStatus.QUEUED, SunatStatus.PENDING])
                ).limit(50)
            )
            invoices = [(str(row[0]), str(row[1])) for row in result.all()]

        for inv_id, cl_id in invoices:
            emit_invoice_task.delay(inv_id, cl_id)

        logger.info(f"Encolados {len(invoices)} comprobantes pendientes")

    asyncio.run(_process())
