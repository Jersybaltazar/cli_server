"""
Modelo Appointment — Citas médicas con state machine de estados.

Estados válidos y transiciones:
    scheduled → confirmed → in_progress → completed
    scheduled → cancelled
    confirmed → cancelled
    in_progress → completed
    confirmed → no_show
    scheduled → no_show
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppointmentStatus(str, enum.Enum):
    """Estados de una cita médica."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


# ── Transiciones válidas de la state machine ─────────
VALID_TRANSITIONS: dict[AppointmentStatus, list[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: [
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.CONFIRMED: [
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.IN_PROGRESS: [
        AppointmentStatus.COMPLETED,
    ],
    # Estados terminales: no tienen transiciones
    AppointmentStatus.COMPLETED: [],
    AppointmentStatus.NO_SHOW: [],
    AppointmentStatus.CANCELLED: [],
}


def is_valid_transition(current: AppointmentStatus, new: AppointmentStatus) -> bool:
    """Verifica si una transición de estado es válida."""
    return new in VALID_TRANSITIONS.get(current, [])


class Appointment(Base):
    __tablename__ = "appointments"

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

    # ── Datos de la cita ─────────────────────────────
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus),
        nullable=False,
        default=AppointmentStatus.SCHEDULED,
    )
    service_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Tipo de servicio: consulta, control, procedimiento, etc."
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # ── Metadata de cancelación ──────────────────────
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

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

    # ── Índices para consultas frecuentes ────────────
    __table_args__ = (
        Index("idx_appointment_clinic_date", "clinic_id", "start_time"),
        Index("idx_appointment_doctor_date", "doctor_id", "start_time"),
        Index("idx_appointment_patient", "patient_id", "start_time"),
        Index("idx_appointment_status", "clinic_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Appointment {self.id} [{self.status.value}] {self.start_time}>"
