"""
Schemas para el catálogo CIE-10.
"""

from uuid import UUID

from pydantic import BaseModel


class CIE10SearchResult(BaseModel):
    """Resultado de búsqueda CIE-10."""
    code: str
    description: str
    category: str | None = None

    model_config = {"from_attributes": True}


class CIE10ListResponse(BaseModel):
    """Respuesta paginada del catálogo CIE-10."""
    items: list[CIE10SearchResult]
    total: int
    page: int
    size: int
    pages: int
