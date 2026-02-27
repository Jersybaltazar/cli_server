"""
Modelo Service — Catálogo de servicios por clínica.

Cada clínica gestiona su propio catálogo de servicios médicos
(consultas, tratamientos, procedimientos) con duración y precio.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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


class ServiceCategory(str, enum.Enum):
    """Categorías de servicios médicos."""
    CONSULTATION = "consultation"
    ECOGRAPHY = "ecography"
    PROCEDURE = "procedure"
    LAB_EXTERNAL = "lab_external"
    SURGERY = "surgery"
    CPN = "cpn"
    VACCINATION = "vaccination"
    OTHER = "other"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    code: Mapped[str | None] = mapped_column(
        String(20), comment="Código interno del servicio (ej: ECO-GEN, CONS-GIN)"
    )
    name: Mapped[str] = mapped_column(
        String(150), nullable=False,
        comment="Nombre del servicio"
    )
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[ServiceCategory] = mapped_column(
        Enum(ServiceCategory), nullable=False, default=ServiceCategory.OTHER,
        comment="Categoría del servicio"
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
        comment="Duración estimada en minutos"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"),
        comment="Precio de venta al paciente en PEN"
    )
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"),
        comment="Precio de costo (pago a proveedor/doctor) en PEN"
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
        Index("idx_service_clinic_category", "clinic_id", "category"),
        UniqueConstraint("clinic_id", "name", name="uq_service_clinic_name"),
    )

    def __repr__(self) -> str:
        return f"<Service {self.name} [{self.category.value}] S/{self.price}>"
