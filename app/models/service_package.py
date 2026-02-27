"""
Modelos ServicePackage + PackageItem — Paquetes de servicios médicos.

Permite agrupar servicios (ej: paquete CPN) con precios totales,
ítems incluidos y opcionalmente programación automática de controles.
"""

import enum
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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ServicePackage(Base):
    __tablename__ = "service_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Precio total del paquete"
    )
    valid_from_week: Mapped[int | None] = mapped_column(
        SmallInteger,
        comment="Semana gestacional mínima para inscripción (solo CPN)"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_schedule: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="Si True, genera citas automáticas al inscribir paciente"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────
    items: Mapped[list["PackageItem"]] = relationship(
        "PackageItem", back_populates="package", cascade="all, delete-orphan",
        order_by="PackageItem.gestational_week_target"
    )

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_service_package_clinic_name"),
        Index("idx_service_package_clinic", "clinic_id"),
    )

    def __repr__(self) -> str:
        return f"<ServicePackage {self.id} {self.name}>"


class PackageItem(Base):
    __tablename__ = "package_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_packages.id", ondelete="CASCADE"),
        nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    description_override: Mapped[str | None] = mapped_column(
        String(200),
        comment="Descripción personalizada que reemplaza el nombre del servicio"
    )
    gestational_week_target: Mapped[int | None] = mapped_column(
        SmallInteger,
        comment="Semana gestacional objetivo para auto-agendar"
    )

    # ── Relationships ────────────────────
    package: Mapped["ServicePackage"] = relationship(
        "ServicePackage", back_populates="items"
    )
    service: Mapped["Service"] = relationship("Service")  # noqa: F821

    __table_args__ = (
        Index("idx_package_item_package", "package_id"),
    )

    def __repr__(self) -> str:
        return f"<PackageItem {self.id} pkg={self.package_id}>"
