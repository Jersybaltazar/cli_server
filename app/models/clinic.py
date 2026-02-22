"""
Modelo Clinic — Tenant principal del sistema multi-tenant.
"""

import uuid
from datetime import datetime

import re
import unicodedata

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Clinic(Base):
    __tablename__ = "clinics"
    __table_args__ = (
        UniqueConstraint("organization_id", "branch_name", name="uq_clinic_branch_name_per_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True,
        comment="Organización a la que pertenece (null = clínica independiente)"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(
        String(100), comment="Nombre de la sede/sucursal (ej: Sede Lima Norte)"
    )
    ruc: Mapped[str] = mapped_column(
        String(11), nullable=False, index=True
    )
    address: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str | None] = mapped_column(
        String(250), unique=True, index=True,
        comment="URL-friendly identifier for public booking (e.g. clinica-san-martin)"
    )
    specialty_type: Mapped[str | None] = mapped_column(
        String(100), comment="general, dental, obstetric, ophthalmic, etc."
    )
    timezone: Mapped[str] = mapped_column(String(50), default="America/Lima")
    logo_url: Mapped[str | None] = mapped_column(String(500))
    settings: Mapped[dict | None] = mapped_column(
        JSONB, default=dict, comment="Configuraciones personalizadas de la clínica"
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    organization: Mapped["Organization | None"] = relationship(  # noqa: F821
        "Organization", back_populates="clinics"
    )
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        "User", back_populates="clinic", lazy="selectin"
    )
    patients: Mapped[list["Patient"]] = relationship(  # noqa: F821
        "Patient", back_populates="clinic", lazy="selectin"
    )
    user_accesses: Mapped[list["UserClinicAccess"]] = relationship(  # noqa: F821
        "UserClinicAccess", back_populates="clinic", lazy="selectin"
    )

    @property
    def display_name(self) -> str:
        """Nombre completo con sucursal si aplica."""
        if self.branch_name:
            return f"{self.name} - {self.branch_name}"
        return self.name

    @staticmethod
    def generate_slug(name: str) -> str:
        """Generate a URL-friendly slug from a clinic name."""
        # Normalize unicode chars (á → a, ñ → n, etc.)
        text = unicodedata.normalize("NFKD", name)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text).strip("-")
        return text or "clinica"

    def __repr__(self) -> str:
        branch = f" ({self.branch_name})" if self.branch_name else ""
        return f"<Clinic {self.name}{branch} (RUC: {self.ruc})>"
