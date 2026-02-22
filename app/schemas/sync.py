"""
Schemas para sincronización offline.

El flujo es:
1. Cliente acumula operaciones en IndexedDB (syncQueue)
2. Al reconectar, envía un SyncBatch al servidor
3. Servidor procesa cada SyncOperation, resuelve conflictos
4. Retorna SyncResponse con: applied, conflicts, updates
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Operación individual ─────────────────────────────

class SyncOperation(BaseModel):
    """Una operación creada offline en el dispositivo."""
    entity: Literal[
        "patient", "appointment", "record",
        "dental_chart", "prenatal_visit", "ophthalmic_exam",
        "invoice",
    ]
    action: Literal["create", "update"]
    local_id: str = Field(
        ..., description="UUID generado en el cliente para la entidad"
    )
    data: dict = Field(
        ..., description="Payload de la entidad (los mismos campos del schema Create/Update)"
    )
    timestamp: datetime = Field(
        ..., description="Momento en que se realizó la operación en el dispositivo"
    )


# ── Batch de operaciones ─────────────────────────────

class SyncBatch(BaseModel):
    """Batch de operaciones enviado desde un dispositivo offline."""
    device_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Identificador único del dispositivo"
    )
    operations: list[SyncOperation] = Field(
        ..., min_length=1, max_length=500,
        description="Operaciones a sincronizar (máximo 500 por batch)"
    )
    last_sync: datetime = Field(
        ..., description="Timestamp de la última sincronización exitosa del dispositivo"
    )


# ── Resultado por operación ──────────────────────────

class SyncApplied(BaseModel):
    """Resultado de una operación aplicada exitosamente."""
    local_id: str
    server_id: str
    entity: str
    action: str
    status: str = "applied"


class SyncConflict(BaseModel):
    """Detalle de un conflicto detectado durante la sincronización."""
    local_id: str
    entity: str
    action: str
    status: str = "conflict"
    reason: str
    server_version: dict | None = Field(
        None, description="Versión actual del registro en el servidor"
    )


class SyncError(BaseModel):
    """Detalle de una operación que falló."""
    local_id: str
    entity: str
    action: str
    status: str = "error"
    error: str


# ── Actualización del servidor ───────────────────────

class SyncServerUpdate(BaseModel):
    """Un registro que cambió en el servidor desde la última sincronización."""
    entity: str
    server_id: str
    action: Literal["create", "update", "delete"]
    data: dict
    updated_at: datetime


# ── Respuesta completa ───────────────────────────────

class SyncResponse(BaseModel):
    """Respuesta del endpoint de sincronización."""
    batch_id: UUID = Field(
        ..., description="ID del batch procesado (para tracking)"
    )
    applied: list[SyncApplied] = Field(
        default=[], description="Operaciones aplicadas exitosamente"
    )
    conflicts: list[SyncConflict] = Field(
        default=[], description="Operaciones con conflictos (resueltos por last-write-wins)"
    )
    errors: list[SyncError] = Field(
        default=[], description="Operaciones que fallaron"
    )
    updates: list[SyncServerUpdate] = Field(
        default=[], description="Cambios del servidor desde la última sincronización del dispositivo"
    )
    server_time: datetime = Field(
        ..., description="Timestamp del servidor al procesar (usar como last_sync en el próximo batch)"
    )
    summary: str = ""


# ── Estado de sincronización ─────────────────────────

class SyncStatusResponse(BaseModel):
    """Estado de sincronización de un dispositivo."""
    device_id: str
    last_sync: datetime | None = None
    pending_batches: int = 0
    total_mappings: int = 0
