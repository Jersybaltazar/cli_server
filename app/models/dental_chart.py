"""
Modelo DentalChart — Odontograma con sistema FDI.

Cada registro representa una entrada de tratamiento/condición
para un diente específico. El historial se construye con múltiples
registros por diente a lo largo del tiempo (versionado).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ToothCondition(str, enum.Enum):
    """Condiciones dentales estándar."""
    HEALTHY = "healthy"
    CARIES = "caries"
    FILLED = "filled"
    EXTRACTED = "extracted"
    MISSING = "missing"
    CROWN = "crown"
    BRIDGE = "bridge"
    IMPLANT = "implant"
    ROOT_CANAL = "root_canal"
    FRACTURE = "fracture"
    SEALANT = "sealant"
    TEMPORARY = "temporary"


class ToothSurface(str, enum.Enum):
    """Superficies dentales (notación estándar)."""
    VESTIBULAR = "V"
    LINGUAL = "L"
    MESIAL = "M"
    DISTAL = "D"
    OCLUSAL = "O"
    INCISAL = "I"
    PALATINO = "P"


class DentalChart(Base):
    __tablename__ = "dental_charts"

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

    # ── Datos del diente (FDI) ───────────────────────
    tooth_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="Número FDI: 11-18, 21-28, 31-38, 41-48 (adulto) / 51-55, 61-65, 71-75, 81-85 (deciduo)"
    )
    surfaces: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(2)),
        comment="Superficies afectadas: ['V','O','M','D','L']"
    )
    condition: Mapped[ToothCondition] = mapped_column(
        Enum(ToothCondition), nullable=False
    )
    treatment: Mapped[str | None] = mapped_column(
        String(200), comment="Tratamiento realizado"
    )
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
        Index("idx_dental_patient_tooth", "patient_id", "tooth_number"),
        Index("idx_dental_clinic_patient", "clinic_id", "patient_id"),
    )

    def __repr__(self) -> str:
        return f"<DentalChart tooth={self.tooth_number} [{self.condition.value}]>"
