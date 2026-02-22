"""
Modelo PrenatalVisit — Control prenatal estándar CLAP/SIP.

Cada registro representa una visita de control prenatal con
todos los datos requeridos por el estándar CLAP/SIP del
Centro Latinoamericano de Perinatología.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PrenatalVisit(Base):
    __tablename__ = "prenatal_visits"

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

    # ── Datos de control prenatal (CLAP/SIP) ─────────
    gestational_week: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="Semana de gestación al momento del control"
    )
    weight: Mapped[float | None] = mapped_column(
        Float, comment="Peso en kg"
    )
    blood_pressure_systolic: Mapped[int | None] = mapped_column(
        SmallInteger, comment="Presión arterial sistólica (mmHg)"
    )
    blood_pressure_diastolic: Mapped[int | None] = mapped_column(
        SmallInteger, comment="Presión arterial diastólica (mmHg)"
    )
    uterine_height: Mapped[float | None] = mapped_column(
        Float, comment="Altura uterina en cm"
    )
    fetal_heart_rate: Mapped[int | None] = mapped_column(
        SmallInteger, comment="Frecuencia cardíaca fetal (lpm)"
    )
    presentation: Mapped[str | None] = mapped_column(
        String(50),
        comment="Presentación fetal: cefálica, podálica, transversa"
    )
    fetal_movements: Mapped[str | None] = mapped_column(
        String(50), comment="Movimientos fetales: positivo, negativo, disminuido"
    )
    edema: Mapped[str | None] = mapped_column(
        String(50), comment="Edema: ausente, leve, moderado, severo"
    )

    # ── Laboratorios y datos adicionales (JSONB) ─────
    labs: Mapped[dict | None] = mapped_column(
        JSONB, default=dict,
        comment="Laboratorios: hemoglobina, glucosa, orina, VIH, RPR, grupo sanguíneo, etc."
    )

    # ── Notas ────────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(Text)
    next_appointment_notes: Mapped[str | None] = mapped_column(
        String(500), comment="Indicaciones para próxima cita"
    )

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
        Index("idx_prenatal_patient", "clinic_id", "patient_id"),
        Index("idx_prenatal_week", "patient_id", "gestational_week"),
    )

    @property
    def blood_pressure(self) -> str | None:
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return None

    def __repr__(self) -> str:
        return f"<PrenatalVisit week={self.gestational_week}>"
