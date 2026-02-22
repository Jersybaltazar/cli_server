"""
Modelo SyncQueue — Cola de operaciones offline pendientes.

Almacena batches de operaciones enviados desde dispositivos
offline que necesitan ser procesados y aplicados en la DB.

Modelo SyncDeviceMapping — Mapeo local_id ↔ server_id.

Cuando un dispositivo crea un registro offline, genera un UUID local.
Al sincronizar, el servidor crea el registro real y guarda el mapeo
para que el dispositivo pueda actualizar sus referencias locales.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SyncStatus(str, enum.Enum):
    """Estados de un batch de sincronización."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"       # Algunas operaciones fallaron
    FAILED = "failed"


class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Identificador único del dispositivo que envía el batch"
    )

    # ── Datos del batch ──────────────────────────────
    operations: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        comment="Array de operaciones: [{entity, action, local_id, data, timestamp}]"
    )
    operation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Cantidad de operaciones en el batch"
    )

    # ── Estado y resultados ──────────────────────────
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus), nullable=False, default=SyncStatus.PENDING
    )
    result: Mapped[dict | None] = mapped_column(
        JSONB, default=dict,
        comment="Resultado del procesamiento: {applied, conflicts, errors}"
    )
    error_message: Mapped[str | None] = mapped_column(String(2000))

    # ── Timestamps ───────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Momento en que se terminó de procesar el batch"
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    user: Mapped["User"] = relationship("User")  # noqa: F821

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_sync_queue_clinic_status", "clinic_id", "status"),
        Index("idx_sync_queue_device", "device_id", "created_at"),
        Index("idx_sync_queue_user", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SyncQueue {self.id} [{self.status.value}] ops={self.operation_count}>"


class SyncDeviceMapping(Base):
    __tablename__ = "sync_device_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    # ── Mapeo de IDs ─────────────────────────────────
    entity: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Tipo de entidad: patient, appointment, record, etc."
    )
    local_id: Mapped[str] = mapped_column(
        String(36), nullable=False,
        comment="UUID generado en el dispositivo cliente"
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
        comment="UUID real del registro en el servidor"
    )

    # ── Timestamps ───────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_mapping_local", "clinic_id", "device_id", "entity", "local_id", unique=True),
        Index("idx_mapping_server", "server_id"),
    )

    def __repr__(self) -> str:
        return f"<SyncMapping {self.entity} local={self.local_id} → server={self.server_id}>"
