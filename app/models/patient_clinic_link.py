"""
Modelo PatientClinicLink — Tabla pivote para registro de pacientes multi-sede.

Registra en qué sedes/sucursales está registrado un paciente dentro de una organización.
Un paciente se crea una sola vez a nivel de organización, y esta tabla
indica en qué sedes ha sido atendido o registrado.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PatientClinicLink(Base):
    """
    Tabla pivote: registra en qué clínicas/sedes está registrado un paciente.

    Cuando un paciente se registra en Sede A, se crea un link para Sede A.
    Si luego se detecta el mismo DNI en Sede B (misma org), no se duplica
    el paciente: solo se crea un nuevo link para Sede B.
    """
    __tablename__ = "patient_clinic_links"
    __table_args__ = (
        UniqueConstraint("patient_id", "clinic_id", name="uq_patient_clinic_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="Fecha en que el paciente fue registrado en esta sede"
    )
    registered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Usuario que registró al paciente en esta sede"
    )

    # ── Relaciones ───────────────────────────────────
    patient: Mapped["Patient"] = relationship(  # noqa: F821
        "Patient", back_populates="clinic_links"
    )
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PatientClinicLink patient={self.patient_id} clinic={self.clinic_id}>"
