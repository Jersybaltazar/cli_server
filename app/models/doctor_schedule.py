"""
Modelo DoctorSchedule — Horarios de atención por doctor.

Define los bloques de disponibilidad semanal de cada doctor.
Se usa para calcular slots disponibles al agendar citas.
"""

import uuid
from datetime import time

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Time,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # ── Día de la semana (0=Lunes ... 6=Domingo) ─────
    day_of_week: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo"
    )

    # ── Bloque de horario ────────────────────────────
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # ── Duración de cada slot en minutos ─────────────
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
        comment="Duración de cada slot de cita en minutos"
    )

    # ── Estado ───────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    doctor: Mapped["User"] = relationship("User")  # noqa: F821

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_schedule_doctor_day", "doctor_id", "day_of_week"),
        Index("idx_schedule_clinic", "clinic_id", "is_active"),
    )

    def __repr__(self) -> str:
        days = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        day_name = days[self.day_of_week] if 0 <= self.day_of_week <= 6 else "?"
        return f"<Schedule {day_name} {self.start_time}-{self.end_time} ({self.slot_duration_minutes}min)>"
