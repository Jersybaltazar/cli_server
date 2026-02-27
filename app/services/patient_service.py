"""
Servicio de pacientes: CRUD con cifrado PII, audit log y soporte cross-sede.

Cuando una clínica pertenece a una organización, los pacientes se comparten
entre todas las sedes de esa org. Un paciente se crea una sola vez; si se
intenta registrar el mismo DNI en otra sede, se vincula automáticamente.
"""

import hashlib
import math
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import decrypt_pii, encrypt_pii
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.patient_clinic_link import PatientClinicLink
from app.models.user import User
from app.schemas.patient import (
    PatientClinicInfo,
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)
from app.services.audit_service import log_action


# ── Helpers de hash ──────────────────────────────────


def _compute_dni_hash(clinic_id: UUID, dni: str) -> str:
    """Computa hash SHA-256 de clinic_id+dni para búsqueda per-sede."""
    raw = f"{clinic_id}:{dni}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _compute_org_dni_hash(org_id: UUID, dni: str) -> str:
    """Computa hash SHA-256 de org_id+dni para dedup cross-sede."""
    raw = f"{org_id}:{dni}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Helpers de contexto ──────────────────────────────


async def _get_clinic_org_id(db: AsyncSession, clinic_id: UUID) -> UUID | None:
    """Obtiene el organization_id de una clínica (None si independiente)."""
    result = await db.execute(
        select(Clinic.organization_id).where(Clinic.id == clinic_id)
    )
    return result.scalar_one_or_none()


async def _build_clinic_links_info(patient: Patient) -> list[PatientClinicInfo]:
    """Construye info de sedes registradas desde las relaciones cargadas."""
    if not patient.clinic_links:
        return []
    return [
        PatientClinicInfo(
            clinic_id=link.clinic_id,
            clinic_name=link.clinic.display_name if link.clinic else None,
            registered_at=link.registered_at,
        )
        for link in patient.clinic_links
    ]


def _patient_to_response(
    patient: Patient,
    registered_sedes: list[PatientClinicInfo] | None = None,
) -> PatientResponse:
    """Convierte un modelo Patient a su schema de respuesta, descifrando PII."""
    return PatientResponse(
        id=patient.id,
        clinic_id=patient.clinic_id,
        organization_id=patient.organization_id,
        dni=decrypt_pii(patient.dni),
        first_name=patient.first_name,
        last_name=patient.last_name,
        full_name=patient.full_name,
        birth_date=patient.birth_date,
        gender=patient.gender,
        phone=decrypt_pii(patient.phone) if patient.phone else None,
        email=decrypt_pii(patient.email) if patient.email else None,
        address=patient.address,
        blood_type=patient.blood_type,
        allergies=patient.allergies,
        emergency_contact_name=patient.emergency_contact_name,
        emergency_contact_phone=(
            decrypt_pii(patient.emergency_contact_phone)
            if patient.emergency_contact_phone
            else None
        ),
        notes=patient.notes,
        fur=patient.fur,
        is_active=patient.is_active,
        registered_sedes=registered_sedes,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


# ── Crear paciente ───────────────────────────────────


async def _create_clinic_link(
    db: AsyncSession,
    patient_id: UUID,
    clinic_id: UUID,
    user_id: UUID | None = None,
) -> None:
    """Crea un PatientClinicLink si no existe."""
    existing = await db.execute(
        select(PatientClinicLink).where(
            PatientClinicLink.patient_id == patient_id,
            PatientClinicLink.clinic_id == clinic_id,
        )
    )
    if not existing.scalar_one_or_none():
        link = PatientClinicLink(
            patient_id=patient_id,
            clinic_id=clinic_id,
            registered_by=user_id,
        )
        db.add(link)
        await db.flush()


async def create_patient(
    db: AsyncSession,
    user: User,
    data: PatientCreate,
    ip_address: str | None = None,
) -> PatientResponse:
    """
    Crea un nuevo paciente con PII cifrado.

    Si la clínica pertenece a una organización:
    - Verifica si el DNI ya existe en CUALQUIER sede de la org
    - Si existe, vincula al paciente con la sede actual (PatientClinicLink)
    - Si no existe, crea el paciente con organization_id y org_dni_hash
    """
    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    # 1. Verificar duplicado en la sede actual
    dni_hash = _compute_dni_hash(clinic_id, data.dni)
    existing_local = await db.execute(
        select(Patient).where(Patient.dni_hash == dni_hash)
    )
    if existing_local.scalar_one_or_none():
        raise ConflictException("Ya existe un paciente con ese DNI en esta sede")

    # 2. Si tiene organización, buscar cross-sede
    if org_id:
        org_hash = _compute_org_dni_hash(org_id, data.dni)
        existing_org = await db.execute(
            select(Patient).where(Patient.org_dni_hash == org_hash)
        )
        existing_patient = existing_org.scalar_one_or_none()

        if existing_patient:
            # Paciente ya existe en otra sede → vincular a esta sede
            await _create_clinic_link(db, existing_patient.id, clinic_id, user.id)

            await log_action(
                db,
                clinic_id=clinic_id,
                user_id=user.id,
                entity="patient",
                entity_id=str(existing_patient.id),
                action="link_to_sede",
                new_data={
                    "clinic_id": str(clinic_id),
                    "origin_clinic_id": str(existing_patient.clinic_id),
                },
                ip_address=ip_address,
            )

            sedes = await _build_clinic_links_info(existing_patient)
            return _patient_to_response(existing_patient, registered_sedes=sedes)

    # 3. Crear paciente nuevo
    patient = Patient(
        clinic_id=clinic_id,
        organization_id=org_id,
        dni=encrypt_pii(data.dni),
        dni_hash=dni_hash,
        org_dni_hash=_compute_org_dni_hash(org_id, data.dni) if org_id else None,
        first_name=data.first_name,
        last_name=data.last_name,
        birth_date=data.birth_date,
        gender=data.gender,
        phone=encrypt_pii(data.phone) if data.phone else None,
        email=encrypt_pii(data.email) if data.email else None,
        address=data.address,
        blood_type=data.blood_type,
        allergies=data.allergies,
        emergency_contact_name=data.emergency_contact_name,
        emergency_contact_phone=(
            encrypt_pii(data.emergency_contact_phone)
            if data.emergency_contact_phone
            else None
        ),
        notes=data.notes,
    )
    db.add(patient)
    await db.flush()

    # Crear link para la sede actual
    await _create_clinic_link(db, patient.id, clinic_id, user.id)

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="patient",
        entity_id=str(patient.id),
        action="create",
        new_data={"first_name": data.first_name, "last_name": data.last_name},
        ip_address=ip_address,
    )

    return _patient_to_response(patient)


# ── Obtener paciente ─────────────────────────────────


async def get_patient(
    db: AsyncSession,
    patient_id: UUID,
    clinic_id: UUID,
) -> PatientResponse:
    """
    Obtiene un paciente por ID.
    Permite acceso si el paciente pertenece a la misma org que la clínica.
    """
    org_id = await _get_clinic_org_id(db, clinic_id)

    _eager = selectinload(Patient.clinic_links).selectinload(PatientClinicLink.clinic)

    if org_id:
        # Cross-sede: permitir si el paciente pertenece a la misma org
        result = await db.execute(
            select(Patient)
            .options(_eager)
            .where(
                Patient.id == patient_id,
                Patient.organization_id == org_id,
            )
        )
    else:
        # Clínica independiente: solo pacientes propios
        result = await db.execute(
            select(Patient)
            .options(_eager)
            .where(
                Patient.id == patient_id,
                Patient.clinic_id == clinic_id,
            )
        )

    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundException("Paciente")

    sedes = await _build_clinic_links_info(patient)
    return _patient_to_response(patient, registered_sedes=sedes)


# ── Listar pacientes ─────────────────────────────────


async def list_patients(
    db: AsyncSession,
    clinic_id: UUID,
    *,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> PatientListResponse:
    """
    Lista pacientes con paginación y filtros.
    Si la clínica tiene organización, muestra pacientes de toda la org.
    """
    org_id = await _get_clinic_org_id(db, clinic_id)

    if org_id:
        # Cross-sede: pacientes de toda la organización
        query = select(Patient).where(Patient.organization_id == org_id)
    else:
        # Clínica independiente
        query = select(Patient).where(Patient.clinic_id == clinic_id)

    # Filtro por estado
    if is_active is not None:
        query = query.where(Patient.is_active == is_active)

    # Búsqueda por nombre o DNI
    if search:
        search_term = f"%{search.lower()}%"
        conditions = [
            func.lower(Patient.first_name).like(search_term),
            func.lower(Patient.last_name).like(search_term),
        ]
        cleaned = search.strip()
        if cleaned.isdigit():
            if org_id:
                # Buscar por org_dni_hash (cross-sede)
                org_hash = _compute_org_dni_hash(org_id, cleaned)
                conditions.append(Patient.org_dni_hash == org_hash)
            else:
                # Buscar por dni_hash (per-sede)
                dni_hash = _compute_dni_hash(clinic_id, cleaned)
                conditions.append(Patient.dni_hash == dni_hash)
        query = query.where(or_(*conditions))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginación
    offset = (page - 1) * size
    query = query.order_by(Patient.last_name, Patient.first_name)
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    patients = result.scalars().all()

    return PatientListResponse(
        items=[_patient_to_response(p) for p in patients],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


# ── Buscar por DNI ───────────────────────────────────


async def search_by_dni(
    db: AsyncSession,
    clinic_id: UUID,
    dni: str,
) -> PatientResponse | None:
    """
    Busca un paciente por DNI.
    Si la clínica tiene organización, busca cross-sede por org_dni_hash.
    """
    org_id = await _get_clinic_org_id(db, clinic_id)

    if org_id:
        org_hash = _compute_org_dni_hash(org_id, dni)
        result = await db.execute(
            select(Patient).where(Patient.org_dni_hash == org_hash)
        )
    else:
        dni_hash = _compute_dni_hash(clinic_id, dni)
        result = await db.execute(
            select(Patient).where(
                Patient.dni_hash == dni_hash,
                Patient.clinic_id == clinic_id,
            )
        )

    patient = result.scalar_one_or_none()
    if not patient:
        return None

    sedes = await _build_clinic_links_info(patient)
    return _patient_to_response(patient, registered_sedes=sedes)


# ── Actualizar paciente ──────────────────────────────


async def update_patient(
    db: AsyncSession,
    patient_id: UUID,
    user: User,
    data: PatientUpdate,
    ip_address: str | None = None,
) -> PatientResponse:
    """
    Actualiza un paciente existente.
    Permite actualización si el paciente pertenece a la misma org.
    """
    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    if org_id:
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.organization_id == org_id,
            )
        )
    else:
        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.clinic_id == clinic_id,
            )
        )

    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundException("Paciente")

    # Guardar datos anteriores para audit
    old_data = {
        "first_name": patient.first_name,
        "last_name": patient.last_name,
    }

    # Actualizar campos no nulos
    update_data = data.model_dump(exclude_unset=True)
    new_data_log = {}

    for field, value in update_data.items():
        if value is not None:
            # Cifrar campos PII
            if field in ("phone", "email", "emergency_contact_phone") and value:
                setattr(patient, field, encrypt_pii(value))
            else:
                setattr(patient, field, value)
            new_data_log[field] = value if field not in ("phone", "email") else "***"

    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="patient",
        entity_id=str(patient.id),
        action="update",
        old_data=old_data,
        new_data=new_data_log,
        ip_address=ip_address,
    )

    await db.refresh(patient)
    return _patient_to_response(patient)
