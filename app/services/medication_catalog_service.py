"""
Servicio del catálogo de medicamentos (Fase 2 — Hito 2.2).

Búsqueda fuzzy con ILIKE sobre dci/commercial_name (índice GIN trgm).
Si una receta usa texto libre (sin id), `medication_id` queda en NULL.
"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medication_catalog import MedicationCatalog
from app.schemas.medication import (
    MedicationCatalogStats,
    MedicationListResponse,
    MedicationSearchResult,
)


async def search_medications(
    db: AsyncSession,
    *,
    q: str | None = None,
    controlled: bool | None = None,
    essential: bool | None = None,
    limit: int = 20,
) -> MedicationListResponse:
    """
    Busca medicamentos por DCI o nombre comercial. Soporta filtros por
    controlled / essential. Ordena coincidencias por prefijo de DCI primero.
    """
    stmt = select(MedicationCatalog).where(
        MedicationCatalog.is_active.is_(True)
    )

    if controlled is not None:
        stmt = stmt.where(MedicationCatalog.is_controlled.is_(controlled))
    if essential is not None:
        stmt = stmt.where(MedicationCatalog.is_essential.is_(essential))

    if q:
        term = q.strip()
        if term:
            pattern = f"%{term}%"
            stmt = stmt.where(
                or_(
                    MedicationCatalog.dci.ilike(pattern),
                    MedicationCatalog.commercial_name.ilike(pattern),
                )
            ).order_by(
                MedicationCatalog.dci.ilike(f"{term}%").desc(),
                MedicationCatalog.dci.asc(),
            )
    else:
        stmt = stmt.order_by(MedicationCatalog.dci.asc())

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return MedicationListResponse(
        items=[MedicationSearchResult.model_validate(r) for r in rows],
        total=len(rows),
    )


async def get_medication(
    db: AsyncSession, medication_id: UUID
) -> MedicationSearchResult | None:
    result = await db.execute(
        select(MedicationCatalog).where(
            MedicationCatalog.id == medication_id,
            MedicationCatalog.is_active.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return MedicationSearchResult.model_validate(row)


async def medication_exists(
    db: AsyncSession, medication_id: UUID
) -> bool:
    result = await db.execute(
        select(MedicationCatalog.id).where(
            MedicationCatalog.id == medication_id,
            MedicationCatalog.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


async def get_stats(db: AsyncSession) -> MedicationCatalogStats:
    total = (
        await db.execute(
            select(func.count()).select_from(MedicationCatalog).where(
                MedicationCatalog.is_active.is_(True)
            )
        )
    ).scalar() or 0
    essential = (
        await db.execute(
            select(func.count()).select_from(MedicationCatalog).where(
                MedicationCatalog.is_active.is_(True),
                MedicationCatalog.is_essential.is_(True),
            )
        )
    ).scalar() or 0
    controlled = (
        await db.execute(
            select(func.count()).select_from(MedicationCatalog).where(
                MedicationCatalog.is_active.is_(True),
                MedicationCatalog.is_controlled.is_(True),
            )
        )
    ).scalar() or 0
    return MedicationCatalogStats(
        total=total, essential=essential, controlled=controlled
    )
