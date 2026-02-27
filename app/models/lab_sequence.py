"""
Modelo LabSequence — Secuencias auto-incrementales para códigos de laboratorio.

Genera códigos como M26-01, M26-02 (patología) y C26-01, C26-02 (citología)
usando SELECT FOR UPDATE para evitar duplicados en concurrencia.
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


class LabSequence(Base):
    __tablename__ = "lab_sequences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    sequence_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="pathology o cytology"
    )
    year: Mapped[int] = mapped_column(
        SmallInteger, nullable=False
    )
    last_number: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "sequence_type", "year",
            name="uq_lab_sequence_clinic_type_year"
        ),
    )

    def __repr__(self) -> str:
        return f"<LabSequence {self.sequence_type} {self.year} #{self.last_number}>"
