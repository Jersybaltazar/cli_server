"""
Endpoints de configuración y gestión de SMS (Twilio).
GET/PUT config, historial de mensajes, envío de prueba.
"""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.dependencies import require_role
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.clinic import Clinic
from app.models.sms_message import SmsMessage, SmsStatus, SmsType
from app.models.user import User, UserRole
from app.schemas.sms import (
    SmsConfigResponse,
    SmsConfigUpdate,
    SmsMessageListResponse,
    SmsMessageResponse,
    SmsPatientEmbed,
    SmsTestRequest,
    SmsTestResponse,
)
from app.services.sms_service import SMSError, send_sms

router = APIRouter()

# Roles con acceso a configuración SMS
_ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)

# Defaults para la configuración SMS
_SMS_DEFAULTS = SmsConfigResponse().model_dump()


# ── GET /config ───────────────────────────────────────

@router.get("/config", response_model=SmsConfigResponse)
async def get_sms_config(
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Retorna la configuración SMS de la clínica."""
    result = await db.execute(
        select(Clinic.settings).where(Clinic.id == user.clinic_id)
    )
    clinic_settings = result.scalar_one_or_none()

    sms_config = {}
    if clinic_settings and isinstance(clinic_settings, dict):
        sms_config = clinic_settings.get("sms", {})

    # Merge defaults con config guardada
    merged = {**_SMS_DEFAULTS, **sms_config}
    return SmsConfigResponse(**merged)


# ── PUT /config ───────────────────────────────────────

@router.put("/config", response_model=SmsConfigResponse)
async def update_sms_config(
    data: SmsConfigUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la configuración SMS de la clínica."""
    result = await db.execute(
        select(Clinic).where(Clinic.id == user.clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clinica no encontrada")

    current_settings = clinic.settings or {}
    current_sms = current_settings.get("sms", {})

    # Aplicar solo campos enviados (no nulos)
    update_data = data.model_dump(exclude_unset=True)
    current_sms.update(update_data)

    current_settings["sms"] = current_sms
    clinic.settings = current_settings

    await db.flush()
    await db.refresh(clinic)

    # Retornar config completa con defaults
    merged = {**_SMS_DEFAULTS, **current_sms}
    return SmsConfigResponse(**merged)


# ── GET /messages ─────────────────────────────────────

@router.get("/messages", response_model=SmsMessageListResponse)
async def get_sms_messages(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role(*_ADMIN_ROLES, UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Historial de mensajes SMS enviados por la clínica."""
    base_filter = SmsMessage.clinic_id == user.clinic_id

    # Count total
    count_result = await db.execute(
        select(func.count(SmsMessage.id)).where(base_filter)
    )
    total = count_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * size
    result = await db.execute(
        select(SmsMessage)
        .options(joinedload(SmsMessage.patient))
        .where(base_filter)
        .order_by(SmsMessage.sent_at.desc())
        .offset(offset)
        .limit(size)
    )
    messages = result.scalars().unique().all()

    items = []
    for msg in messages:
        patient_embed = None
        if msg.patient:
            patient_embed = SmsPatientEmbed(
                first_name=msg.patient.first_name,
                last_name=msg.patient.last_name,
            )

        items.append(SmsMessageResponse(
            id=msg.id,
            patient_id=msg.patient_id,
            phone=msg.phone,
            message=msg.message,
            sms_type=msg.sms_type.value,
            status=msg.status.value,
            sent_at=msg.sent_at,
            error_message=msg.error_message,
            patient=patient_embed,
        ))

    return SmsMessageListResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
    )


# ── POST /test ────────────────────────────────────────

@router.post("/test", response_model=SmsTestResponse)
async def send_test_sms(
    data: SmsTestRequest,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Envía un SMS de prueba al número proporcionado."""
    # Obtener nombre de la clínica
    result = await db.execute(
        select(Clinic.name).where(Clinic.id == user.clinic_id)
    )
    clinic_name = result.scalar_one_or_none() or "Clínica"

    test_message = (
        f"Mensaje de prueba de {clinic_name}. "
        f"Si recibiste este mensaje, la configuración SMS está correcta. "
        f"— ClinicSaaS"
    )

    try:
        sms_result = await send_sms(data.phone, test_message)

        # Guardar en historial
        sms_record = SmsMessage(
            clinic_id=user.clinic_id,
            patient_id=None,
            sent_by=user.id,
            phone=data.phone,
            message=test_message,
            sms_type=SmsType.TEST,
            status=SmsStatus.SIMULATED if sms_result.get("status") == "simulated" else SmsStatus.SENT,
            twilio_sid=sms_result.get("sid"),
        )
        db.add(sms_record)
        await db.flush()

        return SmsTestResponse(
            success=True,
            message="SMS de prueba enviado correctamente",
            twilio_sid=sms_result.get("sid"),
        )

    except SMSError as e:
        # Guardar intento fallido en historial
        sms_record = SmsMessage(
            clinic_id=user.clinic_id,
            patient_id=None,
            sent_by=user.id,
            phone=data.phone,
            message=test_message,
            sms_type=SmsType.TEST,
            status=SmsStatus.FAILED,
            error_message=e.message,
        )
        db.add(sms_record)
        await db.flush()

        return SmsTestResponse(
            success=False,
            message=f"Error al enviar SMS: {e.message}",
        )
