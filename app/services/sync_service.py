"""
Servicio de sincronización offline: procesamiento de batches,
resolución de conflictos (last-write-wins) y mapeo de IDs.

Flujo:
1. Recibir SyncBatch con operaciones offline
2. Por cada operación:
   a. CREATE → crear el registro, guardar mapeo local_id ↔ server_id
   b. UPDATE → buscar por local_id (via mapping) o server_id,
      aplicar last-write-wins comparando timestamps
3. Recolectar cambios del servidor desde last_sync
4. Retornar SyncResponse con applied, conflicts, errors, updates
"""

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_pii
from app.models.appointment import Appointment, AppointmentStatus
from app.models.dental_chart import DentalChart
from app.models.medical_record import MedicalRecord
from app.models.ophthalmic_exam import OphthalmicExam
from app.models.patient import Patient
from app.models.prenatal_visit import PrenatalVisit
from app.models.sync_queue import SyncDeviceMapping, SyncQueue, SyncStatus
from app.models.user import User
from app.schemas.sync import (
    SyncApplied,
    SyncBatch,
    SyncConflict,
    SyncError,
    SyncOperation,
    SyncResponse,
    SyncServerUpdate,
    SyncStatusResponse,
)

logger = logging.getLogger(__name__)


# ── Procesar batch completo ──────────────────────────

async def process_sync_batch(
    db: AsyncSession,
    user: User,
    batch: SyncBatch,
) -> SyncResponse:
    """
    Procesa un batch completo de operaciones offline.
    Guarda el batch en sync_queue para tracking y procesa cada operación.
    """
    clinic_id = user.clinic_id
    now = datetime.now(timezone.utc)

    # Registrar el batch en la cola
    queue_entry = SyncQueue(
        clinic_id=clinic_id,
        user_id=user.id,
        device_id=batch.device_id,
        operations={"operations": [op.model_dump(mode="json") for op in batch.operations]},
        operation_count=len(batch.operations),
        status=SyncStatus.PROCESSING,
    )
    db.add(queue_entry)
    await db.flush()

    applied: list[SyncApplied] = []
    conflicts: list[SyncConflict] = []
    errors: list[SyncError] = []

    # Procesar cada operación
    for operation in batch.operations:
        try:
            result = await _process_operation(
                db, clinic_id, user, batch.device_id, operation
            )
            if isinstance(result, SyncApplied):
                applied.append(result)
            elif isinstance(result, SyncConflict):
                conflicts.append(result)
        except Exception as e:
            logger.error(f"Error procesando operación {operation.local_id}: {e}")
            errors.append(SyncError(
                local_id=operation.local_id,
                entity=operation.entity,
                action=operation.action,
                error=str(e),
            ))

    # Obtener actualizaciones del servidor
    updates = await _get_server_updates(
        db, clinic_id, batch.last_sync
    )

    # Actualizar estado del batch
    status = SyncStatus.COMPLETED
    if errors:
        status = SyncStatus.PARTIAL if applied else SyncStatus.FAILED

    queue_entry.status = status
    queue_entry.processed_at = now
    queue_entry.result = {
        "applied_count": len(applied),
        "conflicts_count": len(conflicts),
        "errors_count": len(errors),
        "updates_count": len(updates),
    }
    if errors:
        queue_entry.error_message = f"{len(errors)} operaciones fallaron"
    await db.flush()

    total = len(applied) + len(conflicts) + len(errors)
    summary = (
        f"Procesadas {total} operaciones: "
        f"{len(applied)} aplicadas, "
        f"{len(conflicts)} conflictos, "
        f"{len(errors)} errores, "
        f"{len(updates)} actualizaciones del servidor"
    )

    return SyncResponse(
        batch_id=queue_entry.id,
        applied=applied,
        conflicts=conflicts,
        errors=errors,
        updates=updates,
        server_time=now,
        summary=summary,
    )


# ── Procesar una operación individual ────────────────

async def _process_operation(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    device_id: str,
    op: SyncOperation,
) -> SyncApplied | SyncConflict:
    """Procesa una operación individual de sincronización."""

    if op.action == "create":
        return await _handle_create(db, clinic_id, user, device_id, op)
    elif op.action == "update":
        return await _handle_update(db, clinic_id, user, device_id, op)
    else:
        raise ValueError(f"Acción no soportada: {op.action}")


# ── CREATE ───────────────────────────────────────────

async def _handle_create(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    device_id: str,
    op: SyncOperation,
) -> SyncApplied | SyncConflict:
    """
    Maneja operaciones CREATE offline.
    Crea el registro real y guarda el mapeo local_id ↔ server_id.
    """

    # Verificar si ya existe un mapeo (deduplicación de reenvío)
    existing_mapping = await _get_mapping(db, clinic_id, device_id, op.entity, op.local_id)
    if existing_mapping:
        return SyncApplied(
            local_id=op.local_id,
            server_id=str(existing_mapping.server_id),
            entity=op.entity,
            action="create",
            status="already_applied",
        )

    # Crear el registro según la entidad
    server_id = await _create_entity(db, clinic_id, user, op)

    # Guardar mapeo
    mapping = SyncDeviceMapping(
        clinic_id=clinic_id,
        device_id=device_id,
        entity=op.entity,
        local_id=op.local_id,
        server_id=server_id,
    )
    db.add(mapping)
    await db.flush()

    return SyncApplied(
        local_id=op.local_id,
        server_id=str(server_id),
        entity=op.entity,
        action="create",
    )


async def _create_entity(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    op: SyncOperation,
) -> UUID:
    """Crea un registro en la entidad correspondiente."""
    data = op.data

    if op.entity == "patient":
        dni = data.get("dni", "")
        dni_hash = hashlib.sha256(f"{clinic_id}:{dni}".encode()).hexdigest()
        patient = Patient(
            clinic_id=clinic_id,
            dni=encrypt_pii(dni),
            dni_hash=dni_hash,
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            birth_date=data.get("birth_date"),
            gender=data.get("gender"),
            phone=encrypt_pii(data["phone"]) if data.get("phone") else None,
            email=encrypt_pii(data["email"]) if data.get("email") else None,
            address=data.get("address"),
            blood_type=data.get("blood_type"),
            allergies=data.get("allergies"),
        )
        db.add(patient)
        await db.flush()
        return patient.id

    elif op.entity == "appointment":
        appointment = Appointment(
            clinic_id=clinic_id,
            patient_id=UUID(data["patient_id"]),
            doctor_id=UUID(data.get("doctor_id", str(user.id))),
            start_time=data["start_time"],
            end_time=data["end_time"],
            status=AppointmentStatus.SCHEDULED,
            service_type=data.get("service_type", "consulta"),
            notes=data.get("notes"),
        )
        db.add(appointment)
        await db.flush()
        return appointment.id

    elif op.entity == "record":
        record = MedicalRecord(
            clinic_id=clinic_id,
            patient_id=UUID(data["patient_id"]),
            doctor_id=user.id,
            record_type=data.get("record_type", "consultation"),
            cie10_codes=data.get("cie10_codes"),
            content=data.get("content", {}),
            specialty_data=data.get("specialty_data"),
            notes=data.get("notes"),
        )
        db.add(record)
        await db.flush()
        return record.id

    elif op.entity == "dental_chart":
        entry = DentalChart(
            clinic_id=clinic_id,
            patient_id=UUID(data["patient_id"]),
            doctor_id=user.id,
            tooth_number=data["tooth_number"],
            surfaces=data.get("surfaces"),
            condition=data["condition"],
            treatment=data.get("treatment"),
            notes=data.get("notes"),
        )
        db.add(entry)
        await db.flush()
        return entry.id

    elif op.entity == "prenatal_visit":
        visit = PrenatalVisit(
            clinic_id=clinic_id,
            patient_id=UUID(data["patient_id"]),
            doctor_id=user.id,
            gestational_week=data["gestational_week"],
            weight=data.get("weight"),
            blood_pressure_systolic=data.get("blood_pressure_systolic"),
            blood_pressure_diastolic=data.get("blood_pressure_diastolic"),
            uterine_height=data.get("uterine_height"),
            fetal_heart_rate=data.get("fetal_heart_rate"),
            presentation=data.get("presentation"),
            fetal_movements=data.get("fetal_movements"),
            edema=data.get("edema"),
            labs=data.get("labs"),
            notes=data.get("notes"),
        )
        db.add(visit)
        await db.flush()
        return visit.id

    elif op.entity == "ophthalmic_exam":
        exam = OphthalmicExam(
            clinic_id=clinic_id,
            patient_id=UUID(data["patient_id"]),
            doctor_id=user.id,
            eye=data["eye"],
            visual_acuity_uncorrected=data.get("visual_acuity_uncorrected"),
            visual_acuity_corrected=data.get("visual_acuity_corrected"),
            sphere=data.get("sphere"),
            cylinder=data.get("cylinder"),
            axis=data.get("axis"),
            addition=data.get("addition"),
            iop=data.get("iop"),
            extra_data=data.get("extra_data"),
            notes=data.get("notes"),
        )
        db.add(exam)
        await db.flush()
        return exam.id

    else:
        raise ValueError(f"Entidad no soportada para CREATE: {op.entity}")


# ── UPDATE (last-write-wins) ─────────────────────────

async def _handle_update(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    device_id: str,
    op: SyncOperation,
) -> SyncApplied | SyncConflict:
    """
    Maneja operaciones UPDATE offline con last-write-wins.
    Compara el timestamp del cliente con updated_at del servidor.
    """

    # Registros médicos son INSERT-only: no se pueden actualizar
    if op.entity in ("record", "dental_chart", "prenatal_visit", "ophthalmic_exam"):
        return SyncConflict(
            local_id=op.local_id,
            entity=op.entity,
            action="update",
            reason="Registros médicos son inmutables (INSERT-only). Solo se pueden crear nuevos.",
        )

    # Resolver el server_id desde el local_id
    server_id = await _resolve_server_id(db, clinic_id, device_id, op.entity, op.local_id)
    if not server_id:
        return SyncConflict(
            local_id=op.local_id,
            entity=op.entity,
            action="update",
            reason=f"No se encontró el registro en el servidor para local_id={op.local_id}",
        )

    # Obtener el registro actual del servidor
    model_class = _get_model_class(op.entity)
    if not model_class:
        raise ValueError(f"Entidad no soportada para UPDATE: {op.entity}")

    result = await db.execute(
        select(model_class).where(
            model_class.id == server_id,
            model_class.clinic_id == clinic_id,
        )
    )
    server_record = result.scalar_one_or_none()

    if not server_record:
        return SyncConflict(
            local_id=op.local_id,
            entity=op.entity,
            action="update",
            reason="Registro no encontrado en el servidor",
        )

    # Last-Write-Wins: comparar timestamps
    server_updated = getattr(server_record, "updated_at", None)
    if server_updated and server_updated > op.timestamp:
        # El servidor tiene una versión más reciente → conflicto
        return SyncConflict(
            local_id=op.local_id,
            entity=op.entity,
            action="update",
            reason="El servidor tiene una versión más reciente (last-write-wins)",
            server_version=_serialize_record(server_record, op.entity),
        )

    # Aplicar la actualización del cliente
    data = op.data
    for field, value in data.items():
        if hasattr(server_record, field) and field not in ("id", "clinic_id", "created_at"):
            # Cifrar campos PII si corresponde
            if op.entity == "patient" and field in ("dni", "phone", "email", "emergency_contact_phone"):
                if value:
                    value = encrypt_pii(value)
            setattr(server_record, field, value)

    await db.flush()

    return SyncApplied(
        local_id=op.local_id,
        server_id=str(server_id),
        entity=op.entity,
        action="update",
    )


# ── Obtener actualizaciones del servidor ─────────────

async def _get_server_updates(
    db: AsyncSession,
    clinic_id: UUID,
    last_sync: datetime,
) -> list[SyncServerUpdate]:
    """
    Obtiene registros que cambiaron en el servidor después de last_sync.
    El cliente necesita estos cambios para actualizar su IndexedDB.
    """
    updates: list[SyncServerUpdate] = []

    # Pacientes actualizados
    patients_result = await db.execute(
        select(Patient).where(
            Patient.clinic_id == clinic_id,
            Patient.updated_at > last_sync,
        ).limit(200)
    )
    for p in patients_result.scalars().all():
        updates.append(SyncServerUpdate(
            entity="patient",
            server_id=str(p.id),
            action="update" if p.created_at < last_sync else "create",
            data=_serialize_record(p, "patient"),
            updated_at=p.updated_at,
        ))

    # Citas actualizadas
    appts_result = await db.execute(
        select(Appointment).where(
            Appointment.clinic_id == clinic_id,
            Appointment.updated_at > last_sync,
        ).limit(200)
    )
    for a in appts_result.scalars().all():
        updates.append(SyncServerUpdate(
            entity="appointment",
            server_id=str(a.id),
            action="update" if a.created_at < last_sync else "create",
            data=_serialize_record(a, "appointment"),
            updated_at=a.updated_at,
        ))

    # Registros médicos creados (INSERT-only, no se actualizan)
    records_result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.clinic_id == clinic_id,
            MedicalRecord.created_at > last_sync,
        ).limit(200)
    )
    for r in records_result.scalars().all():
        updates.append(SyncServerUpdate(
            entity="record",
            server_id=str(r.id),
            action="create",
            data=_serialize_record(r, "record"),
            updated_at=r.created_at,
        ))

    # Ordenar por timestamp
    updates.sort(key=lambda u: u.updated_at)

    return updates


# ── Helpers ──────────────────────────────────────────

async def _get_mapping(
    db: AsyncSession,
    clinic_id: UUID,
    device_id: str,
    entity: str,
    local_id: str,
) -> SyncDeviceMapping | None:
    """Busca un mapeo existente local_id → server_id."""
    result = await db.execute(
        select(SyncDeviceMapping).where(
            SyncDeviceMapping.clinic_id == clinic_id,
            SyncDeviceMapping.device_id == device_id,
            SyncDeviceMapping.entity == entity,
            SyncDeviceMapping.local_id == local_id,
        )
    )
    return result.scalar_one_or_none()


async def _resolve_server_id(
    db: AsyncSession,
    clinic_id: UUID,
    device_id: str,
    entity: str,
    local_id: str,
) -> UUID | None:
    """
    Resuelve un local_id a su server_id.
    Primero busca en el mapeo, si no lo encuentra,
    intenta usar el local_id como server_id directamente.
    """
    mapping = await _get_mapping(db, clinic_id, device_id, entity, local_id)
    if mapping:
        return mapping.server_id

    # Intentar usar local_id como server_id (si fue creado online)
    try:
        return UUID(local_id)
    except ValueError:
        return None


def _get_model_class(entity: str):
    """Retorna la clase del modelo según el nombre de la entidad."""
    mapping = {
        "patient": Patient,
        "appointment": Appointment,
        "record": MedicalRecord,
        "dental_chart": DentalChart,
        "prenatal_visit": PrenatalVisit,
        "ophthalmic_exam": OphthalmicExam,
    }
    return mapping.get(entity)


def _serialize_record(record, entity: str) -> dict:
    """Serializa un registro a dict para enviar al cliente."""
    from app.core.security import decrypt_pii

    data = {"id": str(record.id)}

    if entity == "patient":
        data.update({
            "dni": decrypt_pii(record.dni) if record.dni else None,
            "first_name": record.first_name,
            "last_name": record.last_name,
            "birth_date": record.birth_date.isoformat() if record.birth_date else None,
            "gender": record.gender,
            "phone": decrypt_pii(record.phone) if record.phone else None,
            "email": decrypt_pii(record.email) if record.email else None,
            "blood_type": record.blood_type,
            "is_active": record.is_active,
        })
    elif entity == "appointment":
        data.update({
            "patient_id": str(record.patient_id),
            "doctor_id": str(record.doctor_id),
            "start_time": record.start_time.isoformat(),
            "end_time": record.end_time.isoformat(),
            "status": record.status.value if hasattr(record.status, "value") else record.status,
            "service_type": record.service_type,
            "notes": record.notes,
        })
    elif entity == "record":
        data.update({
            "patient_id": str(record.patient_id),
            "doctor_id": str(record.doctor_id),
            "record_type": record.record_type.value if hasattr(record.record_type, "value") else record.record_type,
            "cie10_codes": record.cie10_codes,
            "content": record.content,
            "specialty_data": record.specialty_data,
            "signed_at": record.signed_at.isoformat() if record.signed_at else None,
        })

    return data


# ── Estado de sincronización ─────────────────────────

async def get_sync_status(
    db: AsyncSession,
    clinic_id: UUID,
    device_id: str,
) -> SyncStatusResponse:
    """Obtiene el estado de sincronización de un dispositivo."""
    from sqlalchemy import func

    # Último sync exitoso
    last_sync_result = await db.execute(
        select(func.max(SyncQueue.processed_at)).where(
            SyncQueue.clinic_id == clinic_id,
            SyncQueue.device_id == device_id,
            SyncQueue.status.in_([SyncStatus.COMPLETED, SyncStatus.PARTIAL]),
        )
    )
    last_sync = last_sync_result.scalar()

    # Batches pendientes
    pending_result = await db.execute(
        select(func.count()).where(
            SyncQueue.clinic_id == clinic_id,
            SyncQueue.device_id == device_id,
            SyncQueue.status == SyncStatus.PENDING,
        )
    )
    pending_batches = pending_result.scalar() or 0

    # Total de mapeos
    mappings_result = await db.execute(
        select(func.count()).where(
            SyncDeviceMapping.clinic_id == clinic_id,
            SyncDeviceMapping.device_id == device_id,
        )
    )
    total_mappings = mappings_result.scalar() or 0

    return SyncStatusResponse(
        device_id=device_id,
        last_sync=last_sync,
        pending_batches=pending_batches,
        total_mappings=total_mappings,
    )
