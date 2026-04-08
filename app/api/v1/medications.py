"""
Endpoints del catálogo local de medicamentos (Fase 2 — Hito 2.2).

Catálogo global de referencia (sin clinic_id), accesible para cualquier
usuario autenticado. Sembrado vía script con el PNUME.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.medication import (
    MedicationCatalogStats,
    MedicationListResponse,
    MedicationSearchResult,
)
from app.services import medication_catalog_service

router = APIRouter()


@router.get("", response_model=MedicationListResponse)
async def search_medications(
    q: str | None = Query(None, description="DCI o nombre comercial (parcial)"),
    controlled: bool | None = Query(
        None, description="Filtrar por sustancias controladas"
    ),
    essential: bool | None = Query(
        None, description="Filtrar por medicamentos PNUME"
    ),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await medication_catalog_service.search_medications(
        db, q=q, controlled=controlled, essential=essential, limit=limit
    )


@router.get("/stats", response_model=MedicationCatalogStats)
async def catalog_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await medication_catalog_service.get_stats(db)


@router.get("/{medication_id}", response_model=MedicationSearchResult)
async def get_medication(
    medication_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    med = await medication_catalog_service.get_medication(db, medication_id)
    if not med:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    return med
