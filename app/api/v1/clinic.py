"""
Endpoints de configuracion de clinica.
GET/PUT para datos de la clinica del usuario autenticado.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.clinic import Clinic
from app.models.user import User, UserRole
from app.schemas.clinic import (
    BillingConfigResponse,
    BillingConfigUpdate,
    ClinicResponse,
    ClinicUpdate,
)

router = APIRouter()


@router.get("/me", response_model=ClinicResponse)
async def get_my_clinic(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna los datos de la clinica del usuario autenticado."""
    result = await db.execute(
        select(Clinic).where(Clinic.id == user.clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clinica no encontrada")
    return clinic


@router.put("/me", response_model=ClinicResponse)
async def update_my_clinic(
    data: ClinicUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza los datos de la clinica del usuario autenticado.
    Solo accesible para super_admin y clinic_admin.
    """
    result = await db.execute(
        select(Clinic).where(Clinic.id == user.clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clinica no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(clinic, field, value)

    await db.flush()
    await db.refresh(clinic)
    return clinic


# ── Billing config ───────────────────────────────────


@router.get("/me/billing", response_model=BillingConfigResponse)
async def get_billing_config(
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna la configuración de facturación de la clínica.
    El token se muestra ofuscado por seguridad.
    """
    result = await db.execute(
        select(Clinic.settings).where(Clinic.id == user.clinic_id)
    )
    clinic_settings = result.scalar_one_or_none()

    billing = {}
    if clinic_settings and isinstance(clinic_settings, dict):
        billing = clinic_settings.get("billing", {})

    token = billing.get("nubefact_token", "")
    return BillingConfigResponse(
        nubefact_token_configured=bool(token),
        nubefact_token_preview=f"...{token[-8:]}" if len(token) > 8 else None,
    )


@router.put("/me/billing", response_model=BillingConfigResponse)
async def update_billing_config(
    data: BillingConfigUpdate,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Configura el token NubeFact para facturación de esta clínica.
    Cada clínica necesita su propio token (vinculado a su RUC en NubeFact).
    """
    result = await db.execute(
        select(Clinic).where(Clinic.id == user.clinic_id)
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clinica no encontrada")

    # Actualizar settings.billing manteniendo otros settings
    current_settings = clinic.settings or {}
    current_settings["billing"] = {
        **current_settings.get("billing", {}),
        "nubefact_token": data.nubefact_token,
    }
    clinic.settings = current_settings

    await db.flush()

    token = data.nubefact_token
    return BillingConfigResponse(
        nubefact_token_configured=True,
        nubefact_token_preview=f"...{token[-8:]}" if len(token) > 8 else None,
    )
