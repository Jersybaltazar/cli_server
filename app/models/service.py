"""
Modelo Service — Catálogo de servicios por clínica.

Cada clínica gestiona su propio catálogo de servicios médicos
(consultas, tratamientos, procedimientos) con duración y precio.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(150), nullable=False,
        comment="Nombre del servicio"
    )
    description: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
        comment="Duración estimada en minutos"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"),
        comment="Precio del servicio en PEN"
    )
    color: Mapped[str | None] = mapped_column(
        String(7), comment="Color hex para calendario (#3b82f6)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_service_clinic", "clinic_id"),
        UniqueConstraint("clinic_id", "name", name="uq_service_clinic_name"),
    )

    def __repr__(self) -> str:
        return f"<Service {self.name} [{self.duration_minutes}min] S/{self.price}>"
