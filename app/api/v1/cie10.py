"""
Endpoints de búsqueda de códigos CIE-10.
Accesible por doctores, admins y super_admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.cie10 import CIE10ListResponse, CIE10SearchResult
from app.services import cie10_service

router = APIRouter()


@router.get("/search", response_model=list[CIE10SearchResult])
async def search_cie10(
    q: str = Query(..., min_length=2, description="Texto a buscar (código o descripción)"),
    category: str | None = Query(None, description="Filtrar por categoría"),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Busca códigos CIE-10 por texto en código o descripción.
    Soporta filtro por categoría (Odontología, Oftalmología, etc.).
    """
    return await cie10_service.search_cie10(db, q, category=category, limit=limit)


@router.get("/categories", response_model=list[str])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las categorías disponibles en el catálogo CIE-10."""
    return await cie10_service.get_categories(db)


@router.get("/stats", response_model=dict)
async def catalog_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Estadísticas del catálogo CIE-10 (total de códigos y categorías)."""
    return await cie10_service.get_catalog_stats(db)


@router.get("/category/{category}", response_model=CIE10ListResponse)
async def list_by_category(
    category: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista códigos CIE-10 de una categoría con paginación."""
    return await cie10_service.list_by_category(db, category, page=page, size=size)


@router.get("/{code}", response_model=CIE10SearchResult | None)
async def get_cie10_code(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene un código CIE-10 específico por su código."""
    entry = await cie10_service.get_cie10_by_code(db, code)
    if not entry:
        raise HTTPException(status_code=404, detail="Código CIE-10 no encontrado")
    return entry
