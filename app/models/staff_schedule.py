"""
Modelo StaffSchedule — Horarios recurrentes de personal no-médico.

Paralelo a DoctorSchedule, pero para obstetras, recepcionistas, lab, etc.
DoctorSchedule se mantiene intacto para cálculo de slots de citas.
"""

import uuid
from datetime import time

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StaffSchedule(Base):
    __tablename__ = "staff_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Día de la semana (0=Lunes ... 6=Domingo)
    day_of_week: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        comment="0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo"
    )

    # Bloque de horario
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Etiqueta de turno
    shift_label: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="mañana, tarde, noche"
    )

    # Estado
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relaciones
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    user: Mapped["User"] = relationship("User")  # noqa: F821

    # Índices
    __table_args__ = (
        Index("idx_staff_schedule_user_day", "user_id", "day_of_week"),
        Index("idx_staff_schedule_clinic", "clinic_id", "is_active"),
    )

    def __repr__(self) -> str:
        days = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        day_name = days[self.day_of_week] if 0 <= self.day_of_week <= 6 else "?"
        return f"<StaffSchedule {day_name} {self.start_time}-{self.end_time}>"
