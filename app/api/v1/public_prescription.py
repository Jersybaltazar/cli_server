"""
Endpoint público de verificación de recetas (no requiere autenticación).
Fase 2.5 — QR de verificación.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from fastapi import Depends

from app.core.exceptions import NotFoundException
from app.core.security import decrypt_pii, verify_verification_token
from app.database import get_db
from app.models.prescription import Prescription

router = APIRouter()


class PrescriptionVerifyResponse(BaseModel):
    """Datos mínimos públicos de una receta verificada."""
    id: str
    serial_number: str | None = None
    kind: str = "common"
    is_signed: bool = False
    signed_date: str | None = None
    valid_until: str | None = None
    is_valid: bool = False  # True si firmada y no vencida
    clinic_name: str | None = None
    clinic_branch: str | None = None
    doctor_name: str | None = None
    doctor_cmp: str | None = None
    patient_initials: str | None = None
    item_count: int = 0
    status: str = "unknown"  # valid | expired | unsigned


@router.get(
    "/prescriptions/{rx_id}/verify",
    response_model=PrescriptionVerifyResponse,
)
async def verify_prescription(
    rx_id: UUID,
    token: str = Query(..., min_length=8, max_length=8),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifica la autenticidad de una receta médica escaneando el QR.
    No requiere autenticación. Valida token HMAC para evitar enumeración.
    """
    if not verify_verification_token(str(rx_id), token):
        raise NotFoundException("Receta no encontrada o token inválido")

    result = await db.execute(
        select(Prescription)
        .options(
            joinedload(Prescription.clinic),
            joinedload(Prescription.doctor),
            joinedload(Prescription.patient),
            selectinload(Prescription.items),
        )
        .where(Prescription.id == rx_id)
    )
    rx = result.unique().scalar_one_or_none()
    if not rx:
        raise NotFoundException("Receta no encontrada")

    # Determinar estado
    is_signed = rx.signed_at is not None
    is_expired = False
    if rx.valid_until and rx.valid_until < date.today():
        is_expired = True

    if not is_signed:
        status = "unsigned"
    elif is_expired:
        status = "expired"
    else:
        status = "valid"

    # Datos mínimos del paciente (solo iniciales)
    patient_initials = None
    if rx.patient:
        fn = (rx.patient.first_name or "")[0:1].upper()
        ln = (rx.patient.last_name or "")[0:1].upper()
        patient_initials = f"{fn}.{ln}." if fn and ln else None

    # Fecha de firma formateada
    signed_date = None
    if rx.signed_at:
        signed_date = rx.signed_at.strftime("%d/%m/%Y %H:%M")

    valid_until_str = None
    if rx.valid_until:
        valid_until_str = rx.valid_until.strftime("%d/%m/%Y")

    return PrescriptionVerifyResponse(
        id=str(rx.id),
        serial_number=rx.serial_number,
        kind=rx.kind or "common",
        is_signed=is_signed,
        signed_date=signed_date,
        valid_until=valid_until_str,
        is_valid=is_signed and not is_expired,
        clinic_name=rx.clinic.name if rx.clinic else None,
        clinic_branch=rx.clinic.branch_name if rx.clinic else None,
        doctor_name=(
            f"{rx.doctor.first_name} {rx.doctor.last_name}" if rx.doctor else None
        ),
        doctor_cmp=rx.doctor.cmp_number if rx.doctor else None,
        patient_initials=patient_initials,
        item_count=len(rx.items) if rx.items else 0,
        status=status,
    )
