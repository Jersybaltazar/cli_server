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
    """Envía un recordatorio de cita respetando la configuración SMS de la clínica."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.appointment import Appointment, AppointmentStatus
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            log_sms,
            render_template,
            send_message,
            send_sms,
            send_whatsapp,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        # Defaults de la plantilla de recordatorio
        _DEFAULT_REMINDER = (
            "Recordatorio: {patient_name}, tiene cita con {doctor_name} "
            "el {date} a las {time} en {clinic_name}. "
            "Confirme respondiendo SI o cancele con CANCELAR."
        )

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
                logger.info(f"Appointment {appointment_id} cancelado/no-show, omitido")
                return

            if appt.reminder_sent_at is not None:
                logger.info(f"Appointment {appointment_id} ya tiene reminder enviado")
                return

            # ── Leer configuración SMS de la clínica ──────────
            sms_config = {}
            if appt.clinic and appt.clinic.settings:
                sms_config = appt.clinic.settings.get("sms", {})

            # Verificar que SMS esté habilitado
            if not sms_config.get("enabled", False):
                logger.info(f"SMS deshabilitado para clínica {appt.clinic_id}, omitido")
                return

            # Verificar ventana horaria de envío
            now = datetime.now(timezone.utc)
            send_start = sms_config.get("send_time_start", "08:00")
            send_end = sms_config.get("send_time_end", "20:00")
            current_hhmm = now.strftime("%H:%M")
            if not (send_start <= current_hhmm <= send_end):
                logger.info(
                    f"Fuera de ventana horaria ({send_start}-{send_end}), "
                    f"hora actual UTC: {current_hhmm}. Omitido."
                )
                return

            # ── Canal preferido ───────────────────────────────
            preferred = sms_config.get("preferred_channel", channel)

            # ── Teléfono del paciente ─────────────────────────
            phone = decrypt_pii(appt.patient.phone) if appt.patient and appt.patient.phone else None
            if not phone:
                logger.warning(f"Paciente sin teléfono para cita {appointment_id}")
                return

            # ── Construir mensaje desde plantilla ─────────────
            template = sms_config.get("template_reminder", _DEFAULT_REMINDER)
            message = render_template(
                template,
                patient_name=appt.patient.first_name,
                doctor_name=f"Dr. {appt.doctor.last_name}" if appt.doctor else "el médico",
                date=appt.start_time.strftime("%d/%m/%Y"),
                time=appt.start_time.strftime("%H:%M"),
                clinic_name=appt.clinic.name if appt.clinic else "",
            )

            # ── Envío según canal ─────────────────────────────
            async def _dispatch(ch: str) -> dict:
                if ch == "sms":
                    r = await send_sms(phone, message)
                    r["channel"] = "sms"
                    return r
                else:  # whatsapp o fallback
                    return await send_message(phone, message, channel="whatsapp")

            try:
                if preferred == "both":
                    # Enviar por ambos canales; loguear cada uno
                    for ch in ("whatsapp", "sms"):
                        try:
                            r = await _dispatch(ch)
                            st = "simulated" if r.get("status") == "simulated" else "sent"
                            await log_sms(
                                db,
                                clinic_id=appt.clinic_id,
                                patient_id=appt.patient_id,
                                phone=phone,
                                message=message,
                                sms_type="reminder",
                                status=st,
                                channel=ch,
                                twilio_sid=r.get("sid"),
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
                                channel=ch,
                                error_message=e.message,
                            )
                else:
                    r = await _dispatch(preferred)
                    st = "simulated" if r.get("status") == "simulated" else "sent"
                    used_ch = r.get("channel", preferred)
                    await log_sms(
                        db,
                        clinic_id=appt.clinic_id,
                        patient_id=appt.patient_id,
                        phone=phone,
                        message=message,
                        sms_type="reminder",
                        status=st,
                        channel=used_ch,
                        twilio_sid=r.get("sid"),
                    )

                appt.reminder_sent_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Reminder ({preferred}) enviado para cita {appointment_id}")

            except SMSError as e:
                await log_sms(
                    db,
                    clinic_id=appt.clinic_id,
                    patient_id=appt.patient_id,
                    phone=phone,
                    message=message,
                    sms_type="reminder",
                    status="failed",
                    channel=preferred,
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
    Task periódico: envía recordatorios por clínica respetando su config SMS.
    Programar con Celery Beat para ejecutarse cada hora.
    Por cada clínica con SMS habilitado usa su reminder_hours_before para
    calcular la ventana de citas a recordar.
    """
    async def _process():
        from app.database import async_session_factory
        from app.models.appointment import Appointment, AppointmentStatus
        from app.models.clinic import Clinic
        from sqlalchemy import select

        now = datetime.now(timezone.utc)
        total_enqueued = 0

        async with async_session_factory() as db:
            # Obtener todas las clínicas activas con sus settings
            clinics_result = await db.execute(
                select(Clinic.id, Clinic.settings).where(Clinic.is_active.is_(True))
            )
            clinics = clinics_result.all()

            for clinic_id, settings in clinics:
                sms_config = (settings or {}).get("sms", {})

                # Solo clínicas con SMS habilitado
                if not sms_config.get("enabled", False):
                    continue

                hours_before = int(sms_config.get("reminder_hours_before", 24))
                preferred_channel = sms_config.get("preferred_channel", "whatsapp")

                # Ventana: el día objetivo calculado desde ahora + hours_before
                target_date = (now + timedelta(hours=hours_before)).date()
                target_start = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
                target_end = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)

                result = await db.execute(
                    select(Appointment.id).where(
                        Appointment.clinic_id == clinic_id,
                        Appointment.start_time >= target_start,
                        Appointment.start_time <= target_end,
                        Appointment.status.in_([
                            AppointmentStatus.SCHEDULED,
                            AppointmentStatus.CONFIRMED,
                        ]),
                        Appointment.reminder_sent_at.is_(None),
                    )
                )
                appointment_ids = [str(row[0]) for row in result.all()]

                for appt_id in appointment_ids:
                    send_appointment_reminder_task.delay(appt_id, channel=preferred_channel)

                if appointment_ids:
                    logger.info(
                        f"Clínica {clinic_id}: {len(appointment_ids)} reminders encolados "
                        f"({hours_before}h antes, canal={preferred_channel})"
                    )
                    total_enqueued += len(appointment_ids)

        logger.info(f"send_daily_reminders: {total_enqueued} reminders encolados en total")

    asyncio.run(_process())


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="sms.send_confirmation",
)
def send_appointment_confirmation_task(self, appointment_id: str):
    """Envía SMS/WhatsApp de confirmación cuando una cita pasa a estado 'confirmed'."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.appointment import Appointment
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            log_sms,
            render_template,
            send_message,
            send_sms,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        _DEFAULT_CONFIRMATION = (
            "Hola {patient_name}, su cita con {doctor_name} ha sido confirmada "
            "para el {date} a las {time} en {clinic_name}. ¡Lo esperamos!"
        )

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

            sms_config = {}
            if appt.clinic and appt.clinic.settings:
                sms_config = appt.clinic.settings.get("sms", {})

            if not sms_config.get("enabled", False):
                return

            phone = decrypt_pii(appt.patient.phone) if appt.patient and appt.patient.phone else None
            if not phone:
                return

            template = sms_config.get("template_confirmation", _DEFAULT_CONFIRMATION)
            message = render_template(
                template,
                patient_name=appt.patient.first_name,
                doctor_name=f"Dr. {appt.doctor.last_name}" if appt.doctor else "el médico",
                date=appt.start_time.strftime("%d/%m/%Y"),
                time=appt.start_time.strftime("%H:%M"),
                clinic_name=appt.clinic.name if appt.clinic else "",
            )

            preferred = sms_config.get("preferred_channel", "whatsapp")

            async def _dispatch(ch: str) -> dict:
                if ch == "sms":
                    r = await send_sms(phone, message)
                    r["channel"] = "sms"
                    return r
                return await send_message(phone, message, channel="whatsapp")

            try:
                channels = ("whatsapp", "sms") if preferred == "both" else (preferred,)
                for ch in channels:
                    try:
                        r = await _dispatch(ch)
                        st = "simulated" if r.get("status") == "simulated" else "sent"
                        await log_sms(
                            db,
                            clinic_id=appt.clinic_id,
                            patient_id=appt.patient_id,
                            phone=phone,
                            message=message,
                            sms_type="confirmation",
                            status=st,
                            channel=r.get("channel", ch),
                            twilio_sid=r.get("sid"),
                        )
                    except SMSError as e:
                        await log_sms(
                            db,
                            clinic_id=appt.clinic_id,
                            patient_id=appt.patient_id,
                            phone=phone,
                            message=message,
                            sms_type="confirmation",
                            status="failed",
                            channel=ch,
                            error_message=e.message,
                        )

                await db.commit()
                logger.info(f"Confirmación ({preferred}) enviada para cita {appointment_id}")

            except Exception as e:
                await db.rollback()
                logger.error(f"Error enviando confirmación: {e}")
                raise

    try:
        asyncio.run(_send())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="sms.send_invoice_notification",
)
def send_invoice_notification_task(self, invoice_id: str):
    """Envía notificación de comprobante emitido respetando la config SMS de la clínica."""
    from uuid import UUID

    async def _send():
        from app.database import async_session_factory
        from app.models.invoice import Invoice
        from app.core.security import decrypt_pii
        from app.services.sms_service import (
            SMSError,
            log_sms,
            send_message,
            send_sms,
        )
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        _DEFAULT_INVOICE = (
            "Hola {patient_name}, se ha emitido su comprobante {comprobante} "
            "por S/ {total} en {clinic_name}. "
            "Puede solicitar su documento digital en recepción."
        )

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

            sms_config = {}
            if invoice.clinic and invoice.clinic.settings:
                sms_config = invoice.clinic.settings.get("sms", {})

            if not sms_config.get("enabled", False):
                return

            phone = decrypt_pii(invoice.patient.phone) if invoice.patient.phone else None
            if not phone:
                return

            preferred = sms_config.get("preferred_channel", "whatsapp")

            # Mensaje de factura (sin template personalizable — usa texto fijo)
            message = _DEFAULT_INVOICE.format(
                patient_name=invoice.patient.first_name,
                comprobante=invoice.numero_comprobante or "",
                total=str(invoice.total),
                clinic_name=invoice.clinic.name if invoice.clinic else "",
            )

            async def _dispatch(ch: str) -> dict:
                if ch == "sms":
                    r = await send_sms(phone, message)
                    r["channel"] = "sms"
                    return r
                return await send_message(phone, message, channel="whatsapp")

            try:
                channels = ("whatsapp", "sms") if preferred == "both" else (preferred,)
                for ch in channels:
                    try:
                        r = await _dispatch(ch)
                        st = "simulated" if r.get("status") == "simulated" else "sent"
                        await log_sms(
                            db,
                            clinic_id=invoice.clinic_id,
                            patient_id=invoice.patient_id,
                            phone=phone,
                            message=message,
                            sms_type="invoice",
                            status=st,
                            channel=r.get("channel", ch),
                            twilio_sid=r.get("sid"),
                        )
                    except SMSError as e:
                        await log_sms(
                            db,
                            clinic_id=invoice.clinic_id,
                            patient_id=invoice.patient_id,
                            phone=phone,
                            message=message,
                            sms_type="invoice",
                            status="failed",
                            channel=ch,
                            error_message=e.message,
                        )

                await db.commit()
                logger.info(f"Notificación factura {invoice_id} enviada ({preferred})")

            except Exception as e:
                await db.rollback()
                logger.error(f"Error enviando notificación factura: {e}")
                raise

    try:
        asyncio.run(_send())
    except Exception as exc:
        raise self.retry(exc=exc)
