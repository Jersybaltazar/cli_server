"""
Tareas Celery para envío de SMS/WhatsApp vía Twilio.
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
def send_appointment_reminder_task(self, appointment_id: str, channel: str = "whatsapp"):
    """Envía un recordatorio de cita por WhatsApp (o SMS como fallback)."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.appointment import Appointment, AppointmentStatus
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            build_appointment_reminder,
            log_sms,
            send_message,
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

            # Evitar envío duplicado
            if appt.reminder_sent_at is not None:
                logger.info(f"Appointment {appointment_id} ya tiene reminder enviado")
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
                msg_result = await send_message(phone, message, channel=channel)
                status = "simulated" if msg_result.get("status") == "simulated" else "sent"
                used_channel = msg_result.get("channel", channel)

                await log_sms(
                    db,
                    clinic_id=appt.clinic_id,
                    patient_id=appt.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="reminder",
                    status=status,
                    channel=used_channel,
                    twilio_sid=msg_result.get("sid"),
                )

                # Marcar reminder como enviado
                appt.reminder_sent_at = datetime.now(timezone.utc)

                await db.commit()
                logger.info(
                    f"Reminder ({used_channel}) enviado para cita {appointment_id}"
                )

            except SMSError as e:
                await log_sms(
                    db,
                    clinic_id=appt.clinic_id,
                    patient_id=appt.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="reminder",
                    status="failed",
                    channel=channel,
                    error_message=e.message,
                )
                await db.commit()
                logger.error(f"Error enviando reminder: {e.message}")
                raise

    try:
        asyncio.run(_send())
    except Exception as exc:
        logger.error(f"Error en reminder task: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(name="sms.send_daily_reminders")
def send_daily_reminders():
    """
    Task periódico (cron): envía recordatorios para citas de mañana.
    Programar con Celery Beat para ejecutarse diariamente a las 18:00.
    Usa WhatsApp con fallback automático a SMS.
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
                    # Solo citas sin reminder enviado
                    Appointment.reminder_sent_at.is_(None),
                )
            )
            appointment_ids = [str(row[0]) for row in result.all()]

        for appt_id in appointment_ids:
            send_appointment_reminder_task.delay(appt_id, channel="whatsapp")

        logger.info(f"Encolados {len(appointment_ids)} reminders para mañana")

    asyncio.run(_process())


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="sms.send_invoice_notification",
)
def send_invoice_notification_task(self, invoice_id: str, channel: str = "whatsapp"):
    """Envía notificación de comprobante emitido por WhatsApp/SMS."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.invoice import Invoice
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            build_invoice_notification,
            log_sms,
            send_message,
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
                msg_result = await send_message(phone, message, channel=channel)
                status = "simulated" if msg_result.get("status") == "simulated" else "sent"
                used_channel = msg_result.get("channel", channel)

                await log_sms(
                    db,
                    clinic_id=invoice.clinic_id,
                    patient_id=invoice.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="invoice",
                    status=status,
                    channel=used_channel,
                    twilio_sid=msg_result.get("sid"),
                )
                await db.commit()
                logger.info(f"Notificación factura {invoice_id} enviada ({used_channel})")

            except SMSError as e:
                await log_sms(
                    db,
                    clinic_id=invoice.clinic_id,
                    patient_id=invoice.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="invoice",
                    status="failed",
                    channel=channel,
                    error_message=e.message,
                )
                await db.commit()
                logger.error(f"Error enviando notificación factura: {e.message}")
                raise

    try:
        asyncio.run(_send())
    except Exception as exc:
        raise self.retry(exc=exc)
