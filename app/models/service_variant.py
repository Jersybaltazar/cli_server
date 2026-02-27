"""
Modelo ServicePriceVariant — Variantes de precio para servicios.

Permite definir recargos (gemelar, fin de semana, urgencia)
como porcentaje o monto fijo sobre el precio base del servicio.
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
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ModifierType(str, enum.Enum):
    """Tipo de modificador de precio."""
    FIXED_SURCHARGE = "fixed_surcharge"
    PERCENTAGE_SURCHARGE = "percentage_surcharge"


class ServicePriceVariant(Base):
    __tablename__ = "service_price_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Etiqueta de la variante (ej: Gemelar, Fin de semana)"
    )
    modifier_type: Mapped[ModifierType] = mapped_column(
        Enum(ModifierType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    modifier_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Monto fijo o porcentaje según modifier_type"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ────────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    service: Mapped["Service"] = relationship("Service")  # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "service_id", "label",
            name="uq_variant_clinic_service_label"
        ),
        Index("idx_variant_clinic_service", "clinic_id", "service_id"),
    )

    def __repr__(self) -> str:
        return f"<ServicePriceVariant {self.label} {self.modifier_type.value}={self.modifier_value}>"
