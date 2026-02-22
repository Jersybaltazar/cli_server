"""
Modelo AuditLog — Registro de auditoría INMUTABLE.
INSERT-only, sin permisos UPDATE/DELETE.
Retención: 10 años (requisito legal Ley 30024 Art. 15).
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )

    # ── Datos del evento ─────────────────────────────
    entity: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Nombre de la entidad: patient, appointment, record, etc."
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), nullable=False,
        comment="UUID del registro afectado"
    )
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="create, update, delete, login, logout, etc."
    )

    # ── Datos del cambio ─────────────────────────────
    old_data: Mapped[dict | None] = mapped_column(
        JSONB, comment="Snapshot del registro antes del cambio"
    )
    new_data: Mapped[dict | None] = mapped_column(
        JSONB, comment="Snapshot del registro después del cambio"
    )

    # ── Metadata de la request ───────────────────────
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)

    # ── Timestamp inmutable ──────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.entity} {self.entity_id}>"
