"""
Modelo StaffScheduleOverride — Excepciones a horarios recurrentes de personal.

Permite registrar vacaciones, días libres, feriados, cambios de turno
y turnos extra. Se cruza con DoctorSchedule para calcular el
personal efectivo de cada día.
"""

import enum
import uuid
from datetime import date, time, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OverrideType(str, enum.Enum):
    """Tipos de excepción al horario recurrente."""
    DAY_OFF = "day_off"
    VACATION = "vacation"
    HOLIDAY = "holiday"
    SHIFT_CHANGE = "shift_change"
    EXTRA_SHIFT = "extra_shift"


class StaffScheduleOverride(Base):
    __tablename__ = "staff_schedule_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False,
        comment="Médico, obstetra o personal afectado"
    )

    # ── Tipo de override ────────────────────────────
    override_type: Mapped[OverrideType] = mapped_column(
        Enum(OverrideType), nullable=False
    )

    # ── Rango de fechas ─────────────────────────────
    date_start: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Fecha inicio (si es un solo día, start == end)"
    )
    date_end: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Fecha fin"
    )

    # ── Nuevos horarios (si es cambio de turno) ─────
    new_start_time: Mapped[time | None] = mapped_column(
        Time, comment="Hora inicio del nuevo turno (solo para shift_change/extra_shift)"
    )
    new_end_time: Mapped[time | None] = mapped_column(
        Time, comment="Hora fin del nuevo turno (solo para shift_change/extra_shift)"
    )

    # ── Suplente (si aplica) ────────────────────────
    substitute_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"),
        comment="Usuario suplente (opcional)"
    )

    # ── Razón ───────────────────────────────────────
    reason: Mapped[str | None] = mapped_column(
        String(500), comment="Motivo de la excepción"
    )

    # ── Auditoría ───────────────────────────────────
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ──────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[user_id]
    )
    substitute: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[substitute_user_id]
    )
    creator: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )

    # ── Índices ─────────────────────────────────────
    __table_args__ = (
        Index("idx_override_clinic_dates", "clinic_id", "date_start", "date_end"),
        Index("idx_override_user_dates", "user_id", "date_start"),
    )

    def __repr__(self) -> str:
        return (
            f"<StaffScheduleOverride {self.override_type.value} "
            f"{self.date_start}–{self.date_end}>"
        )
