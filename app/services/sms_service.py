"""
Servicio de envío de SMS y WhatsApp vía Twilio.

Envía mensajes de texto para:
- Recordatorios de cita (24h antes, 1h antes)
- Confirmación de cita
- Notificación de factura emitida

Soporta dos canales:
- SMS: Twilio Programmable SMS
- WhatsApp: Twilio WhatsApp API (mismo SDK, prefijo whatsapp:)

Docs SMS: https://www.twilio.com/docs/sms/api/message-resource
Docs WA:  https://www.twilio.com/docs/whatsapp/api
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SMSError(Exception):
    """Error de comunicación con Twilio SMS API."""

    def __init__(self, message: str, sid: str | None = None):
        self.message = message
        self.sid = sid
        super().__init__(message)


async def send_sms(phone_number: str, message: str) -> dict:
    """
    Envía un SMS vía Twilio.
    El número debe incluir código de país con + (ej: +51987654321).

    Args:
        phone_number: Número de destino con código de país.
        message: Contenido del SMS (máximo 1600 caracteres).

    Returns:
        dict con sid, status y detalles del mensaje enviado.
    """
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_PHONE_NUMBER

    # ── Modo simulación (sin credenciales) ───────────
    if (
        not account_sid
        or account_sid == "your-twilio-account-sid"
        or not auth_token
        or auth_token == "your-twilio-auth-token"
    ):
        logger.warning("Twilio credentials no configuradas — simulando envío")
        logger.info(f"[SIMULATED SMS] To: {phone_number} | Message: {message[:80]}...")
        return {
            "sid": "SIMULATED",
            "status": "simulated",
            "to": phone_number,
            "body": message,
        }

    # ── Asegurar formato internacional ───────────────
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"

    # ── Enviar vía Twilio SDK ────────────────────────
    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException

        client = Client(account_sid, auth_token)

        twilio_message = client.messages.create(
            body=message,
            from_=from_number,
            to=phone_number,
        )

        logger.info(
            f"SMS enviado a {phone_number} | SID: {twilio_message.sid} | "
            f"Status: {twilio_message.status}"
        )

        return {
            "sid": twilio_message.sid,
            "status": twilio_message.status,
            "to": twilio_message.to,
            "body": message,
        }

    except TwilioRestException as e:
        logger.error(f"Twilio error ({e.code}): {e.msg}")
        raise SMSError(
            f"Error Twilio ({e.code}): {e.msg}",
            sid=None,
        )
    except Exception as e:
        logger.error(f"Error inesperado enviando SMS: {e}")
        raise SMSError(f"Error enviando SMS: {str(e)}")


async def send_whatsapp(phone_number: str, message: str) -> dict:
    """
    Envía un mensaje WhatsApp vía Twilio.
    Usa el mismo SDK de Twilio; la diferencia es el prefijo whatsapp: en from/to.

    Args:
        phone_number: Número de destino con código de país (+51987654321).
        message: Contenido del mensaje.

    Returns:
        dict con sid, status y detalles del mensaje enviado.
    """
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    wa_from = settings.TWILIO_WHATSAPP_NUMBER

    # ── Modo simulación (sin credenciales) ───────────
    if (
        not account_sid
        or account_sid == "your-twilio-account-sid"
        or not auth_token
        or auth_token == "your-twilio-auth-token"
    ):
        logger.warning("Twilio credentials no configuradas — simulando envío WA")
        logger.info(f"[SIMULATED WA] To: {phone_number} | Message: {message[:80]}...")
        return {
            "sid": "SIMULATED",
            "status": "simulated",
            "to": phone_number,
            "body": message,
            "channel": "whatsapp",
        }

    # ── Asegurar formato internacional ───────────────
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"

    # ── Enviar vía Twilio SDK (WhatsApp) ─────────────
    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException

        client = Client(account_sid, auth_token)

        twilio_message = client.messages.create(
            body=message,
            from_=f"whatsapp:{wa_from}",
            to=f"whatsapp:{phone_number}",
        )

        logger.info(
            f"WhatsApp enviado a {phone_number} | SID: {twilio_message.sid} | "
            f"Status: {twilio_message.status}"
        )

        return {
            "sid": twilio_message.sid,
            "status": twilio_message.status,
            "to": twilio_message.to,
            "body": message,
            "channel": "whatsapp",
        }

    except TwilioRestException as e:
        logger.error(f"Twilio WA error ({e.code}): {e.msg}")
        raise SMSError(
            f"Error Twilio WhatsApp ({e.code}): {e.msg}",
            sid=None,
        )
    except Exception as e:
        logger.error(f"Error inesperado enviando WhatsApp: {e}")
        raise SMSError(f"Error enviando WhatsApp: {str(e)}")


async def send_message(
    phone_number: str,
    message: str,
    channel: str = "whatsapp",
) -> dict:
    """
    Fachada unificada: envía por el canal preferido con fallback.
    Si WhatsApp falla, reintenta por SMS automáticamente.

    Args:
        phone_number: Número con código de país.
        message: Contenido del mensaje.
        channel: "whatsapp" o "sms". Default whatsapp.

    Returns:
        dict con sid, status, channel usado.
    """
    if channel == "whatsapp":
        try:
            return await send_whatsapp(phone_number, message)
        except SMSError:
            logger.warning(
                f"WhatsApp falló para {phone_number}, cayendo a SMS"
            )
            result = await send_sms(phone_number, message)
            result["channel"] = "sms"
            result["fallback"] = True
            return result
    else:
        result = await send_sms(phone_number, message)
        result["channel"] = "sms"
        return result


# ── Mensajes predefinidos ────────────────────────────

def build_appointment_reminder(
    patient_name: str,
    doctor_name: str,
    appointment_time: datetime,
    clinic_name: str,
) -> str:
    """Construye mensaje de recordatorio de cita."""
    time_str = appointment_time.strftime("%d/%m/%Y a las %H:%M")
    return (
        f"Hola {patient_name}, le recordamos que tiene una cita "
        f"con {doctor_name} el {time_str} en {clinic_name}. "
        f"Por favor confirme su asistencia respondiendo SI. "
        f"Para cancelar, responda CANCELAR."
    )


def build_appointment_confirmation(
    patient_name: str,
    doctor_name: str,
    appointment_time: datetime,
    clinic_name: str,
) -> str:
    """Construye mensaje de confirmación de cita reservada."""
    time_str = appointment_time.strftime("%d/%m/%Y a las %H:%M")
    return (
        f"Hola {patient_name}, su cita ha sido confirmada. "
        f"Doctor: {doctor_name}. "
        f"Fecha: {time_str}. "
        f"Clinica: {clinic_name}. "
        f"¡Lo esperamos!"
    )


def build_invoice_notification(
    patient_name: str,
    comprobante: str,
    total: str,
    clinic_name: str,
) -> str:
    """Construye mensaje de notificación de comprobante emitido."""
    return (
        f"Hola {patient_name}, se ha emitido su comprobante "
        f"{comprobante} por S/ {total} en {clinic_name}. "
        f"Puede solicitar su documento digital en recepcion."
    )


# ── Logging de SMS en base de datos ──────────────────

async def log_sms(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    phone: str,
    message: str,
    sms_type: str,
    status: str,
    channel: str = "sms",
    patient_id: UUID | None = None,
    sent_by: UUID | None = None,
    twilio_sid: str | None = None,
    error_message: str | None = None,
) -> None:
    """Registra un mensaje SMS/WhatsApp en la tabla sms_messages."""
    from app.models.sms_message import SmsMessage, SmsStatus, SmsType, MessageChannel

    record = SmsMessage(
        clinic_id=clinic_id,
        patient_id=patient_id,
        sent_by=sent_by,
        phone=phone,
        message=message,
        sms_type=SmsType(sms_type),
        status=SmsStatus(status),
        channel=MessageChannel(channel),
        twilio_sid=twilio_sid,
        error_message=error_message,
    )
    db.add(record)
    await db.flush()
