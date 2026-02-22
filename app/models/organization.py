"""
Modelo Organization — Grupo empresarial que agrupa varias clínicas/sucursales.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlanType(str, enum.Enum):
    """Tipos de plan de suscripción SaaS."""
    BASIC = "basic"              # 1 sede
    PROFESSIONAL = "professional"  # hasta 3 sedes
    ENTERPRISE = "enterprise"    # sedes ilimitadas


class Organization(Base):
    """
    Grupo empresarial que agrupa varias clínicas/sucursales.
    Es la entidad de facturación del SaaS (el cliente que paga).
    """
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Nombre del grupo empresarial"
    )
    ruc: Mapped[str] = mapped_column(
        String(11), unique=True, nullable=False, index=True,
        comment="RUC principal de la organización"
    )
    plan_type: Mapped[PlanType] = mapped_column(
        Enum(PlanType), nullable=False, default=PlanType.BASIC,
        comment="Plan de suscripción SaaS"
    )
    max_clinics: Mapped[int] = mapped_column(
        default=1, comment="Máximo de sedes permitidas según el plan"
    )
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    settings: Mapped[dict | None] = mapped_column(
        JSONB, default=dict, comment="Configuraciones globales de la organización"
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinics: Mapped[list["Clinic"]] = relationship(  # noqa: F821
        "Clinic", back_populates="organization", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} (RUC: {self.ruc}, Plan: {self.plan_type.value})>"
