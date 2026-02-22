"""
Modelo User — Usuarios del sistema con roles RBAC.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """Roles del sistema con permisos jerárquicos."""
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    CLINIC_ADMIN = "clinic_admin"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )

    # ── Datos de acceso ──────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.RECEPTIONIST
    )

    # ── Datos profesionales ──────────────────────────
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cmp_number: Mapped[str | None] = mapped_column(
        String(20), comment="Número de colegiatura médica (CMP)"
    )
    specialty: Mapped[str | None] = mapped_column(
        String(100), comment="Especialidad médica"
    )
    specialty_type: Mapped[str | None] = mapped_column(
        String(100),
        comment="Tipo de especialidad: ginecologo, obstetra, enfermera, tecnico"
    )
    position: Mapped[str | None] = mapped_column(
        String(100),
        comment="Cargo: Médico Ginecólogo, Obstetriz, Recepcionista"
    )
    phone: Mapped[str | None] = mapped_column(String(20))

    # ── MFA ──────────────────────────────────────────
    is_mfa_enabled: Mapped[bool] = mapped_column(default=False)
    mfa_secret: Mapped[str | None] = mapped_column(
        String(255), comment="TOTP secret cifrado"
    )

    # ── Estado ───────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship(  # noqa: F821
        "Clinic", back_populates="users"
    )
    clinic_accesses: Mapped[list["UserClinicAccess"]] = relationship(  # noqa: F821
        "UserClinicAccess", back_populates="user", lazy="selectin"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
