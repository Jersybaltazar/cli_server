"""
Modelo ImagingTemplate — Plantillas reutilizables por clínica.

Permite guardar snapshots de findings + conclusiones + recomendaciones
para un study_type dado, y cargarlos al crear un nuevo informe.
Las plantillas son scoped a clinic_id y son inmutables (se crean y se
eliminan; para "editar" se crea una nueva versión).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.imaging_report import ImagingStudyType


class ImagingTemplate(Base):
    __tablename__ = "imaging_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    study_type: Mapped[ImagingStudyType] = mapped_column(
        Enum(
            ImagingStudyType,
            name="imagingstudytype",
            values_callable=lambda enum: [m.value for m in enum],
            create_type=False,
        ),
        nullable=False,
    )

    findings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    conclusion_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recommendations: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821

    __table_args__ = (
        Index("idx_imaging_tpl_clinic_type", "clinic_id", "study_type"),
    )

    def __repr__(self) -> str:
        return f"<ImagingTemplate {self.name} ({self.study_type.value})>"
