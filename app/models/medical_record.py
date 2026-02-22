"""
Modelo MedicalRecord — Historia Clínica Electrónica (HCE).

INSERT-only por normativa NTS 139-MINSA.
Una vez firmado (signed_at != null), el registro es INMUTABLE.
El campo content (JSONB) permite datos flexibles por especialidad.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecordType(str, enum.Enum):
    """Tipos de registro clínico."""
    CONSULTATION = "consultation"
    CONTROL = "control"
    EMERGENCY = "emergency"
    PROCEDURE = "procedure"
    DENTAL = "dental"
    PRENATAL = "prenatal"
    OPHTHALMIC = "ophthalmic"
    LAB_RESULT = "lab_result"
    IMAGING = "imaging"
    NOTE = "note"


class MedicalRecord(Base):
    __tablename__ = "medical_records"

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
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"),
        comment="Cita asociada (opcional)"
    )

    # ── Tipo y códigos CIE-10 ────────────────────────
    record_type: Mapped[RecordType] = mapped_column(
        Enum(RecordType), nullable=False
    )
    cie10_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(10)),
        comment="Códigos CIE-10 de diagnósticos: ['J06.9', 'R50.9']"
    )

    # ── Contenido flexible ───────────────────────────
    content: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="Contenido clínico flexible: motivo, examen, diagnóstico, plan, etc."
    )
    specialty_data: Mapped[dict | None] = mapped_column(
        JSONB, default=dict,
        comment="Datos específicos de especialidad (odontograma, prenatal, etc.)"
    )

    # ── Notas adicionales ────────────────────────────
    notes: Mapped[str | None] = mapped_column(Text)

    # ── Firma digital ────────────────────────────────
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Timestamp de firma. Una vez firmado, el registro es INMUTABLE"
    )
    signed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Doctor que firmó el registro"
    )

    # ── Timestamps ───────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])  # noqa: F821

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_record_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_record_doctor", "clinic_id", "doctor_id"),
        Index("idx_record_type", "clinic_id", "record_type"),
        Index("idx_record_created", "clinic_id", "created_at"),
    )

    @property
    def is_signed(self) -> bool:
        return self.signed_at is not None

    def __repr__(self) -> str:
        signed = "SIGNED" if self.is_signed else "DRAFT"
        return f"<MedicalRecord {self.record_type.value} [{signed}] {self.created_at}>"
