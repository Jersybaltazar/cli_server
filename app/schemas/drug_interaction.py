"""
Schemas Pydantic para el detector de interacciones medicamentosas (DDI).
"""

from uuid import UUID

from pydantic import BaseModel, Field


class DrugInteractionAlert(BaseModel):
    """Una alerta de interacción entre dos medicamentos."""
    interaction_id: UUID
    drug_a: str
    drug_b: str
    severity: str  # contraindicated | major | moderate | minor
    description: str
    recommendation: str | None = None
    # Índices de los items en la receta (para resaltar en el frontend)
    item_index_a: int | None = None
    item_index_b: int | None = None


class DDICheckRequest(BaseModel):
    """Payload para verificar interacciones de una receta."""
    patient_id: UUID
    items: list["DDICheckItem"] = Field(default_factory=list)
    exclude_prescription_id: UUID | None = None


class DDICheckItem(BaseModel):
    """Un item para verificar interacciones."""
    medication: str = Field(..., min_length=1)
    medication_id: UUID | None = None


class DDICheckResponse(BaseModel):
    """Resultado de la verificación de interacciones."""
    alerts: list[DrugInteractionAlert]
    has_contraindicated: bool = False
    has_major: bool = False
    total: int = 0
