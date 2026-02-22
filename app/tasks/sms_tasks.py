"""
Tareas Celery para envío de SMS vía Twilio.
Recordatorios automáticos y notificaciones.
Registra cada mensaje en sms_messages para historial.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="sms.send_reminder",
)
def send_appointment_reminder_task(self, appointment_id: str):
    """Envía un recordatorio de cita por SMS."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.appointment import Appointment, AppointmentStatus
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            build_appointment_reminder,
            log_sms,
            send_sms,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        async with async_session_factory() as db:
            result = await db.execute(
                select(Appointment)
                .options(
                    joinedload(Appointment.patient),
                    joinedload(Appointment.doctor),
                    joinedload(Appointment.clinic),
                )
                .where(Appointment.id == UUID(appointment_id))
            )
            appt = result.scalar_one_or_none()

            if not appt:
                logger.error(f"Appointment {appointment_id} no encontrado")
                return

            if appt.status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
                logger.info(f"Appointment {appointment_id} cancelado/no-show, no enviar")
                return

            # Obtener teléfono del paciente (descifrando PII)
            phone = decrypt_pii(appt.patient.phone) if appt.patient.phone else None
            if not phone:
                logger.warning(f"Paciente sin teléfono, no se puede enviar reminder")
                return

            # Construir y enviar mensaje
            message = build_appointment_reminder(
                patient_name=appt.patient.first_name,
                doctor_name=f"Dr. {appt.doctor.first_name} {appt.doctor.last_name}",
                appointment_time=appt.start_time,
                clinic_name=appt.clinic.name,
            )

            try:
                sms_result = await send_sms(phone, message)
                status = "simulated" if sms_result.get("status") == "simulated" else "sent"

                await log_sms(
                    db,
                    clinic_id=appt.clinic_id,
                    patient_id=appt.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="reminder",
                    status=status,
                    twilio_sid=sms_result.get("sid"),
                )
                await db.commit()
                logger.info(f"SMS reminder enviado para cita {appointment_id}")

            except SMSError as e:
                await log_sms(
                    db,
                    clinic_id=appt.clinic_id,
                    patient_id=appt.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="reminder",
                    status="failed",
                    error_message=e.message,
                )
                await db.commit()
                logger.error(f"Error enviando SMS reminder: {e.message}")
                raise

    try:
        asyncio.run(_send())
    except Exception as exc:
        logger.error(f"Error en SMS reminder task: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="sms.send_daily_reminders")
def send_daily_reminders():
    """
    Task periódico (cron): envía recordatorios para citas de mañana.
    Programar con Celery Beat para ejecutarse diariamente a las 18:00.
    """
    async def _process():
        from app.database import async_session_factory
        from app.models.appointment import Appointment, AppointmentStatus
        from sqlalchemy import select

        tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow, time.min).replace(tzinfo=timezone.utc)
        tomorrow_end = datetime.combine(tomorrow, time.max).replace(tzinfo=timezone.utc)

        async with async_session_factory() as db:
            result = await db.execute(
                select(Appointment.id).where(
                    Appointment.start_time >= tomorrow_start,
                    Appointment.start_time <= tomorrow_end,
                    Appointment.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                    ]),
                )
            )
            appointment_ids = [str(row[0]) for row in result.all()]

        for appt_id in appointment_ids:
            send_appointment_reminder_task.delay(appt_id)

        logger.info(f"Encolados {len(appointment_ids)} SMS reminders para mañana")

    asyncio.run(_process())


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="sms.send_invoice_notification",
)
def send_invoice_notification_task(self, invoice_id: str):
    """Envía notificación de comprobante emitido por SMS."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.invoice import Invoice
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            build_invoice_notification,
            log_sms,
            send_sms,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        async with async_session_factory() as db:
            result = await db.execute(
                select(Invoice)
                .options(
                    joinedload(Invoice.patient),
                    joinedload(Invoice.clinic),
                )
                .where(Invoice.id == UUID(invoice_id))
            )
            invoice = result.scalar_one_or_none()

            if not invoice or not invoice.patient:
                logger.warning(f"Invoice {invoice_id} sin paciente asociado")
                return

            phone = decrypt_pii(invoice.patient.phone) if invoice.patient.phone else None
            if not phone:
                return

            message = build_invoice_notification(
                patient_name=invoice.patient.first_name,
                comprobante=invoice.numero_comprobante,
                total=str(invoice.total),
                clinic_name=invoice.clinic.name,
            )

            try:
                sms_result = await send_sms(phone, message)
                status = "simulated" if sms_result.get("status") == "simulated" else "sent"

                await log_sms(
                    db,
                    clinic_id=invoice.clinic_id,
                    patient_id=invoice.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="invoice",
                    status=status,
                    twilio_sid=sms_result.get("sid"),
                )
                await db.commit()
                logger.info(f"SMS notificación factura {invoice_id} enviada")

            except SMSError as e:
                await log_sms(
                    db,
                    clinic_id=invoice.clinic_id,
                    patient_id=invoice.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="invoice",
                    status="failed",
                    error_message=e.message,
                )
                await db.commit()
                logger.error(f"Error enviando SMS factura: {e.message}")
                raise

    try:
        asyncio.run(_send())
    except Exception as exc:
        raise self.retry(exc=exc)
