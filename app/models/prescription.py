"""
Modelos Prescription / PrescriptionItem — Recetas médicas comunes.

Cada receta pertenece a una clínica y a un paciente, es emitida por un médico
y agrupa una lista de medicamentos (PrescriptionItem). Mismo patrón que
ImagingReport: soporte de firma digital + inmutabilidad post-firma.

Fase 1 — Recetas comunes (no cubre psicotrópicos/estupefacientes, los cuales
requieren numeración controlada y formulario oficial DIGEMID).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from datetime import date as date_type
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

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
        comment="MedicalRecord asociado (opcional)"
    )

    # ── Datos clínicos ──────────────────────────────
    diagnosis: Mapped[str | None] = mapped_column(
        Text, comment="Diagnóstico clínico (texto libre)"
    )
    cie10_code: Mapped[str | None] = mapped_column(
        String(10), comment="Código CIE-10 principal"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, comment="Indicaciones generales / notas al pie"
    )

    # ── Numeración correlativa (Fase 2.1) ───────────
    serial_number: Mapped[str | None] = mapped_column(
        String(32),
        comment="Serial RX-AAAA-NNNNNN (común) o RXC-AAAA-NNNNNN (controlada)"
    )

    # ── Tipo de receta (Fase 2.3) ───────────────────
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="common", server_default="common",
        comment="Tipo de receta: common | controlled (DS 023-2001-SA)"
    )
    valid_until: Mapped[date_type | None] = mapped_column(
        Date,
        comment="Vigencia máxima (3 días para controladas, derivado al firmar)"
    )

    # ── DDI override — interacciones aceptadas (Fase 2.4) ──
    acknowledged_interactions: Mapped[list | None] = mapped_column(
        JSONB,
        comment="Interacciones major/contraindicated aceptadas al firmar (auditoría)"
    )

    # ── Verificación QR (Fase 2.5) ─────────────────────
    verification_token: Mapped[str | None] = mapped_column(
        String(16),
        comment="HMAC-SHA256 truncado para URL pública de verificación QR"
    )

    # ── Firma digital ───────────────────────────────
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Fecha y hora de firma. Si != NULL la receta es inmutable."
    )
    signed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Médico que firmó la receta."
    )

    # ── Timestamps ──────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ──────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])  # noqa: F821
    signer: Mapped["User"] = relationship("User", foreign_keys=[signed_by])  # noqa: F821
    record: Mapped["MedicalRecord"] = relationship("MedicalRecord")  # noqa: F821
    items: Mapped[list["PrescriptionItem"]] = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.position",
    )

    __table_args__ = (
        Index("idx_prescription_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_prescription_created", "clinic_id", "created_at"),
        Index("idx_prescription_signed", "clinic_id", "signed_at"),
    )

    @property
    def is_signed(self) -> bool:
        return self.signed_at is not None

    def __repr__(self) -> str:
        return f"<Prescription {self.id} {self.created_at}>"


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Vínculo opcional al catálogo (Fase 2.2) ──────
    medication_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medication_catalog.id"),
        comment="Si proviene del catálogo, FK; si es texto libre, NULL"
    )

    # ── Medicamento (texto libre — DCI o comercial) ──
    medication: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Denominación común internacional o nombre comercial"
    )
    presentation: Mapped[str | None] = mapped_column(
        String(120),
        comment="Forma farmacéutica y concentración (Ej: Tabletas 500 mg)"
    )
    dose: Mapped[str | None] = mapped_column(
        String(120),
        comment="Dosis por toma (Ej: 1 tableta, 5 ml)"
    )
    frequency: Mapped[str | None] = mapped_column(
        String(120),
        comment="Frecuencia (Ej: cada 8 horas)"
    )
    duration: Mapped[str | None] = mapped_column(
        String(120),
        comment="Duración del tratamiento (Ej: por 7 días)"
    )
    quantity: Mapped[str | None] = mapped_column(
        String(60),
        comment="Cantidad total a dispensar (Ej: 21 tabletas)"
    )
    instructions: Mapped[str | None] = mapped_column(
        Text, comment="Indicaciones específicas para este medicamento"
    )

    prescription: Mapped["Prescription"] = relationship(
        "Prescription", back_populates="items"
    )

    __table_args__ = (
        Index("idx_prescription_item_rx", "prescription_id"),
    )


class PrescriptionTemplate(Base):
    """Plantilla reutilizable de receta (recetas frecuentes por clínica)."""

    __tablename__ = "prescription_templates"

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
    diagnosis: Mapped[str | None] = mapped_column(Text)
    cie10_code: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    creator: Mapped["User"] = relationship("User")  # noqa: F821

    __table_args__ = (
        Index("idx_prescription_tpl_clinic", "clinic_id"),
    )
