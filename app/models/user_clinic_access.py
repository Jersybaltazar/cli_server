"""
Modelo UserClinicAccess — Tabla pivote para acceso multi-sede.
Permite que un usuario pueda acceder a múltiples clínicas/sucursales.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import UserRole


class UserClinicAccess(Base):
    """
    Tabla pivote que mapea el acceso de un usuario a múltiples clínicas.

    Un doctor puede atender en Sede Norte (lunes/martes) y Sede Sur (miércoles/jueves).
    Un org_admin tiene acceso a todas las sedes de su organización.
    """
    __tablename__ = "user_clinic_access"
    __table_args__ = (
        UniqueConstraint("user_id", "clinic_id", name="uq_user_clinic_access"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role_in_clinic: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False,
        comment="Rol del usuario en esta sede específica"
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="clinic_accesses"
    )
    clinic: Mapped["Clinic"] = relationship(  # noqa: F821
        "Clinic", back_populates="user_accesses"
    )

    def __repr__(self) -> str:
        return f"<UserClinicAccess user={self.user_id} clinic={self.clinic_id} role={self.role_in_clinic.value}>"
