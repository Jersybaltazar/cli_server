"""
Modelo OphthalmicExam — Examen oftalmológico.

Registra datos de refracción, presión intraocular y agudeza visual
para cada ojo (OD/OS) con campos adicionales en JSONB.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EyeSide(str, enum.Enum):
    """Ojo evaluado."""
    OD = "OD"  # Ojo derecho (Oculus Dexter)
    OS = "OS"  # Ojo izquierdo (Oculus Sinister)


class OphthalmicExam(Base):
    __tablename__ = "ophthalmic_exams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_records.id"),
        comment="Registro médico asociado (opcional)"
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # ── Ojo evaluado ─────────────────────────────────
    eye: Mapped[EyeSide] = mapped_column(
        Enum(EyeSide), nullable=False
    )

    # ── Agudeza visual ───────────────────────────────
    visual_acuity_uncorrected: Mapped[str | None] = mapped_column(
        String(20), comment="AV sin corrección: 20/20, 20/40, etc."
    )
    visual_acuity_corrected: Mapped[str | None] = mapped_column(
        String(20), comment="AV con corrección: 20/20, 20/40, etc."
    )

    # ── Refracción ───────────────────────────────────
    sphere: Mapped[float | None] = mapped_column(
        Float, comment="Esfera (dioptrías): -20.00 a +20.00"
    )
    cylinder: Mapped[float | None] = mapped_column(
        Float, comment="Cilindro (dioptrías): -10.00 a +10.00"
    )
    axis: Mapped[int | None] = mapped_column(
        comment="Eje (grados): 0 a 180"
    )
    addition: Mapped[float | None] = mapped_column(
        Float, comment="Adición para presbicia: +0.50 a +4.00"
    )

    # ── Presión intraocular ──────────────────────────
    iop: Mapped[float | None] = mapped_column(
        Float, comment="Presión intraocular (mmHg): normal 10-21"
    )

    # ── Datos adicionales (JSONB) ────────────────────
    extra_data: Mapped[dict | None] = mapped_column(
        JSONB, default=dict,
        comment="Campos adicionales: fondo de ojo, biomicroscopía, campimetría, etc."
    )

    # ── Notas ────────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(Text)

    # ── Timestamps ───────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    doctor: Mapped["User"] = relationship("User")  # noqa: F821
    record: Mapped["MedicalRecord"] = relationship("MedicalRecord")  # noqa: F821

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_ophthalmic_patient", "clinic_id", "patient_id"),
        Index("idx_ophthalmic_eye", "patient_id", "eye"),
    )

    def __repr__(self) -> str:
        return f"<OphthalmicExam {self.eye.value} IOP={self.iop}>"
