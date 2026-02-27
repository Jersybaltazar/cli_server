"""
Endpoints para gestión de mapeo Procedimiento → Insumos.
Configura qué insumos consume cada servicio/procedimiento.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.procedure_supply import (
    ProcedureSupplyCreate,
    ProcedureSupplyResponse,
    ProcedureSupplyUpdate,
    ProcedureSupplyWithNames,
)
from app.services import procedure_supply_service

router = APIRouter()

_ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)


@router.post("/", response_model=ProcedureSupplyResponse, status_code=201)
async def create_procedure_supply(
    data: ProcedureSupplyCreate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un mapeo servicio → insumo. Solo admin."""
    return await procedure_supply_service.create_procedure_supply(
        db, clinic_id=user.clinic_id, data=data
    )


@router.get("/", response_model=list[ProcedureSupplyWithNames])
async def list_procedure_supplies(
    service_id: UUID | None = Query(None, description="Filtrar por servicio"),
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista mapeos servicio → insumos con nombres enriquecidos."""
    return await procedure_supply_service.list_procedure_supplies(
        db, clinic_id=user.clinic_id, service_id=service_id
    )


@router.patch("/{ps_id}", response_model=ProcedureSupplyResponse)
async def update_procedure_supply(
    ps_id: UUID,
    data: ProcedureSupplyUpdate,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza cantidad o activa/desactiva un mapeo. Solo admin."""
    return await procedure_supply_service.update_procedure_supply(
        db, clinic_id=user.clinic_id, ps_id=ps_id, data=data
    )


@router.delete("/{ps_id}", status_code=204)
async def delete_procedure_supply(
    ps_id: UUID,
    user: User = Depends(require_role(*_ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Elimina un mapeo servicio → insumo. Solo admin."""
    await procedure_supply_service.delete_procedure_supply(
        db, clinic_id=user.clinic_id, ps_id=ps_id
    )
