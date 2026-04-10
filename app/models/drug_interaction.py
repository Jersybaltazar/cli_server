"""
Modelo DrugInteraction — Pares de interacciones medicamentosas.

Tabla de referencia global (sin clinic_id). Cada fila representa una
interacción entre dos DCIs (o códigos ATC) con un nivel de severidad.

Fase 2, Hito 2.4 — Detector DDI.
"""

import uuid

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DrugInteraction(Base):
    __tablename__ = "drug_interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Par de medicamentos (DCI normalizado, lowercase) ──
    drug_a: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="DCI del primer medicamento (normalizado lowercase)"
    )
    drug_b: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="DCI del segundo medicamento (normalizado lowercase)"
    )

    # ── Severidad ──────────────────────────────────────────
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="contraindicated | major | moderate | minor"
    )

    # ── Descripción clínica ────────────────────────────────
    description: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Descripción clínica breve de la interacción"
    )
    recommendation: Mapped[str | None] = mapped_column(
        Text,
        comment="Recomendación clínica (ajustar dosis, monitorear, evitar, etc.)"
    )

    __table_args__ = (
        Index("idx_ddi_drug_a", "drug_a"),
        Index("idx_ddi_drug_b", "drug_b"),
        Index("idx_ddi_pair", "drug_a", "drug_b", unique=True),
    )

    def __repr__(self) -> str:
        return f"<DrugInteraction {self.drug_a} ↔ {self.drug_b} [{self.severity}]>"
