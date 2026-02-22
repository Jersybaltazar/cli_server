"""
Servicio CIE-10: búsqueda de códigos de diagnóstico desde la BD.

Usa la tabla cie10_codes con índice trigram (pg_trgm) para
búsqueda fuzzy en español. Si la tabla está vacía, cae al
catálogo en memoria como fallback.
"""

import math
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cie10 import Cie10Code
from app.schemas.cie10 import CIE10ListResponse, CIE10SearchResult


# ── Búsqueda ─────────────────────────────────────────


async def search_cie10(
    db: AsyncSession,
    query: str,
    *,
    category: str | None = None,
    limit: int = 20,
) -> list[CIE10SearchResult]:
    """
    Busca códigos CIE-10 por texto (código o descripción).
    Usa ILIKE para coincidencia parcial.
    """
    q = query.strip()
    if not q:
        return []

    stmt = select(Cie10Code).where(Cie10Code.is_active.is_(True))

    if category:
        stmt = stmt.where(Cie10Code.category.ilike(f"%{category}%"))

    # Buscar en código o descripción
    pattern = f"%{q}%"
    stmt = stmt.where(
        or_(
            Cie10Code.code.ilike(pattern),
            Cie10Code.description.ilike(pattern),
        )
    )

    # Ordenar: coincidencia exacta de código primero, luego alfabético
    stmt = stmt.order_by(
        # Códigos que empiezan con el query van primero
        Cie10Code.code.ilike(f"{q}%").desc(),
        Cie10Code.code,
    ).limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        CIE10SearchResult(
            code=r.code,
            description=r.description,
            category=r.category,
        )
        for r in rows
    ]


async def get_cie10_by_code(
    db: AsyncSession,
    code: str,
) -> CIE10SearchResult | None:
    """Obtiene un código CIE-10 específico."""
    result = await db.execute(
        select(Cie10Code).where(
            Cie10Code.code == code.upper(),
            Cie10Code.is_active.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None

    return CIE10SearchResult(
        code=row.code,
        description=row.description,
        category=row.category,
    )


async def get_categories(db: AsyncSession) -> list[str]:
    """Retorna todas las categorías únicas del catálogo."""
    result = await db.execute(
        select(Cie10Code.category)
        .where(Cie10Code.is_active.is_(True))
        .distinct()
        .order_by(Cie10Code.category)
    )
    return [row[0] for row in result.fetchall()]


async def list_by_category(
    db: AsyncSession,
    category: str,
    *,
    page: int = 1,
    size: int = 50,
) -> CIE10ListResponse:
    """Lista códigos de una categoría con paginación."""
    base = select(Cie10Code).where(
        Cie10Code.is_active.is_(True),
        Cie10Code.category.ilike(f"%{category}%"),
    )

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginar
    offset = (page - 1) * size
    stmt = base.order_by(Cie10Code.code).offset(offset).limit(size)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return CIE10ListResponse(
        items=[
            CIE10SearchResult(
                code=r.code,
                description=r.description,
                category=r.category,
            )
            for r in rows
        ],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


async def validate_cie10_codes(
    db: AsyncSession,
    codes: list[str],
) -> tuple[list[str], list[str]]:
    """
    Valida una lista de códigos contra la BD.
    Retorna (válidos, inválidos).
    """
    if not codes:
        return [], []

    upper_codes = [c.upper() for c in codes]
    result = await db.execute(
        select(Cie10Code.code).where(
            Cie10Code.code.in_(upper_codes),
            Cie10Code.is_active.is_(True),
        )
    )
    found = {row[0] for row in result.fetchall()}

    valid = [c for c in upper_codes if c in found]
    invalid = [c for c in upper_codes if c not in found]

    return valid, invalid


async def get_catalog_stats(db: AsyncSession) -> dict:
    """Estadísticas del catálogo CIE-10."""
    total_result = await db.execute(
        select(func.count()).select_from(Cie10Code).where(Cie10Code.is_active.is_(True))
    )
    total = total_result.scalar() or 0

    cat_result = await db.execute(
        select(func.count(func.distinct(Cie10Code.category))).where(Cie10Code.is_active.is_(True))
    )
    categories = cat_result.scalar() or 0

    return {
        "total_codes": total,
        "total_categories": categories,
    }
