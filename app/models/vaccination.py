"""
Modelos de Vacunación — Esquemas de vacunas y registro de dosis por paciente.

VaccineScheme: define un esquema de vacuna (nombre, dosis, intervalos).
PatientVaccination: registra cada dosis aplicada a un paciente.
"""

import uuid
from datetime import date, datetime

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VaccineScheme(Base):
    __tablename__ = "vaccine_schemes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True,
        comment="Nombre del esquema de vacuna (ej: Gardasil 9)"
    )
    doses_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Número total de dosis del esquema"
    )
    dose_intervals_months: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Intervalos en meses entre dosis [0, 2, 6]"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<VaccineScheme {self.name} ({self.doses_total} dosis)>"


class PatientVaccination(Base):
    __tablename__ = "patient_vaccinations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    vaccine_scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vaccine_schemes.id"), nullable=False
    )
    dose_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Número de dosis aplicada (1, 2, 3...)"
    )
    administered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="Fecha y hora de aplicación"
    )
    administered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Profesional que aplicó la dosis"
    )
    lot_number: Mapped[str | None] = mapped_column(
        String(50), comment="Número de lote de la vacuna"
    )
    next_dose_date: Mapped[date | None] = mapped_column(
        Date, comment="Fecha estimada para la siguiente dosis"
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"),
        comment="Insumo de inventario vinculado (si aplica)"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ────────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    vaccine_scheme: Mapped["VaccineScheme"] = relationship("VaccineScheme")
    administrator: Mapped["User"] = relationship("User")  # noqa: F821

    __table_args__ = (
        Index("idx_vaccination_patient", "patient_id"),
        Index("idx_vaccination_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_vaccination_next_dose", "next_dose_date"),
    )

    def __repr__(self) -> str:
        return f"<PatientVaccination patient={self.patient_id} dose={self.dose_number}>"
