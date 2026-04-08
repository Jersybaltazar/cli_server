"""
Schemas Pydantic para el catálogo de medicamentos.
"""

from uuid import UUID

from pydantic import BaseModel


class MedicationSearchResult(BaseModel):
    id: UUID
    dci: str
    commercial_name: str | None = None
    form: str | None = None
    concentration: str | None = None
    presentation: str | None = None
    route: str | None = None
    therapeutic_group: str | None = None
    is_essential: bool = False
    is_controlled: bool = False
    controlled_list: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class MedicationListResponse(BaseModel):
    items: list[MedicationSearchResult]
    total: int


class MedicationCatalogStats(BaseModel):
    total: int
    essential: int
    controlled: int
