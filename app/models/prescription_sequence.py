"""
Modelo PrescriptionSequence — Secuencia auto-incremental de recetas por clínica.

Genera seriales como RX-2026-000123 (recetas comunes) y RXC-2026-000123 (recetas
controladas — psicotrópicos/estupefacientes, Fase 2.3). Usa SELECT FOR UPDATE
para evitar duplicados en concurrencia. La secuencia se reinicia cada año.
"""

import uuid

from sqlalchemy import (
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrescriptionSequence(Base):
    __tablename__ = "prescription_sequences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="common o controlled"
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    last_number: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "kind", "year",
            name="uq_prescription_sequence_clinic_kind_year",
        ),
    )

    def __repr__(self) -> str:
        return f"<PrescriptionSequence {self.kind} {self.year} #{self.last_number}>"
