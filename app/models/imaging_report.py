"""
Modelo ImagingReport — Informes de ecografías y procedimientos.

Una sola tabla con discriminador `study_type` y campo `findings` (JSONB)
que contiene la estructura específica de cada tipo de estudio. Permite
agregar nuevos tipos sin migraciones adicionales.

Patrón análogo a PrenatalVisit: vínculo opcional con MedicalRecord mediante
record_id para heredar firma digital e inmutabilidad (NTS 139-MINSA).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImagingStudyType(str, enum.Enum):
    """Tipos de estudio de imagenología soportados."""
    PELVIC = "pelvic"
    TRANSVAGINAL = "transvaginal"
    OBSTETRIC_FIRST = "obstetric_first"
    OBSTETRIC_SECOND_THIRD = "obstetric_second_third"
    OBSTETRIC_DOPPLER = "obstetric_doppler"
    OBSTETRIC_TWIN = "obstetric_twin"
    OBSTETRIC_TWIN_DOPPLER = "obstetric_twin_doppler"
    BREAST = "breast"
    MORPHOLOGIC = "morphologic"
    GENETIC = "genetic"
    HYSTEROSONOGRAPHY = "hysterosonography"
    COLPOSCOPY = "colposcopy"


class ImagingReport(Base):
    __tablename__ = "imaging_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_records.id"),
        comment="MedicalRecord asociado (opcional) para firma digital"
    )

    # ── Tipo y contenido ─────────────────────────────
    study_type: Mapped[ImagingStudyType] = mapped_column(
        Enum(
            ImagingStudyType,
            name="imagingstudytype",
            values_callable=lambda enum: [m.value for m in enum],
        ),
        nullable=False,
    )
    findings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="Estructura específica del tipo de estudio (biometría, medidas, etc.)"
    )
    conclusion_items: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Lista de strings con los ítems de la conclusión"
    )
    recommendations: Mapped[str | None] = mapped_column(Text)

    # ── Firma digital (Fase 5) ───────────────────────
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Fecha y hora de firma. Si != NULL el informe es inmutable."
    )
    signed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Doctor que firmó el informe."
    )

    # ── Timestamps ───────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])  # noqa: F821
    signer: Mapped["User"] = relationship("User", foreign_keys=[signed_by])  # noqa: F821
    record: Mapped["MedicalRecord"] = relationship("MedicalRecord")  # noqa: F821

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_imaging_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_imaging_study_type", "clinic_id", "study_type"),
        Index("idx_imaging_created", "clinic_id", "created_at"),
        Index("idx_imaging_signed", "clinic_id", "signed_at"),
    )

    @property
    def is_signed(self) -> bool:
        return self.signed_at is not None

    def __repr__(self) -> str:
        return f"<ImagingReport {self.study_type.value} {self.created_at}>"
