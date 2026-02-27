"""
Endpoint público de reserva online.
NO requiere autenticación — se accede con el slug de la clínica.
"""

import hashlib
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.core.security import encrypt_pii
from app.database import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic import Clinic
from app.models.doctor_schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User, UserRole
from app.schemas.appointment import (
    AvailabilityResponse,
    PublicBookingRequest,
    PublicBookingResponse,
    TimeSlot,
)
from app.services.appointment_service import _check_overlap, _generate_slots

router = APIRouter()


# ── Schemas para la info pública ──────────────────────────

class ServicePublicItem(BaseModel):
    id: str
    name: str
    duration_minutes: int
    price: float
    description: str | None = None


class DoctorPublicItem(BaseModel):
    id: str
    name: str  # Frontend compatible
    first_name: str
    last_name: str
    specialty: str | None = None
    cmp_number: str | None = None


class ClinicPublicInfoResponse(BaseModel):
    id: str
    name: str
    slug: str
    address: str | None = None
    phone: str | None = None
    specialty_type: str | None = None
    logo_url: str | None = None
    services: list[ServicePublicItem] = []
    doctors: list[DoctorPublicItem] = []


# ── Helpers ───────────────────────────────────────────────

async def _get_clinic_by_slug(
    slug: str,
    db: AsyncSession,
) -> Clinic:
    """Valida que la clínica existe, está activa y tiene ese slug."""
    result = await db.execute(
        select(Clinic).where(Clinic.slug == slug, Clinic.is_active.is_(True))
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clínica")
    return clinic


async def _get_clinic_by_id(
    clinic_id: UUID,
    db: AsyncSession,
) -> Clinic:
    """Valida que la clínica existe y está activa (mantener retrocompatibilidad)."""
    result = await db.execute(
        select(Clinic).where(Clinic.id == clinic_id, Clinic.is_active.is_(True))
    )
    clinic = result.scalar_one_or_none()
    if not clinic:
        raise NotFoundException("Clínica")
    return clinic


async def _get_public_doctors(
    clinic_id: UUID,
    db: AsyncSession,
) -> list[DoctorPublicItem]:
    """Obtiene lista de doctores activos para una clínica."""
    result = await db.execute(
        select(User).where(
            User.clinic_id == clinic_id,
            User.role.in_([UserRole.DOCTOR, UserRole.OBSTETRA]),
            User.is_active.is_(True),
        )
    )
    doctors = result.scalars().all()
    return [
        DoctorPublicItem(
            id=str(d.id),
            name=f"Dr. {d.first_name} {d.last_name}",
            first_name=d.first_name,
            last_name=d.last_name,
            specialty=d.specialty,
            cmp_number=d.cmp_number,
        )
        for d in doctors
    ]


# ── Endpoints públicos ────────────────────────────────────

@router.get("/info/{slug}", response_model=ClinicPublicInfoResponse)
async def get_clinic_public_info(
    slug: str = Path(..., description="Slug de la clínica"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna información pública de la clínica (nombre, dirección,
    servicios activos, doctores disponibles).
    No requiere autenticación.
    """
    clinic = await _get_clinic_by_slug(slug, db)

    # Obtener servicios activos
    services_result = await db.execute(
        select(Service).where(
            Service.clinic_id == clinic.id,
            Service.is_active.is_(True),
        )
    )
    services = services_result.scalars().all()

    # Obtener doctores
    doctors = await _get_public_doctors(clinic.id, db)

    return ClinicPublicInfoResponse(
        id=str(clinic.id),
        name=clinic.display_name,
        slug=clinic.slug or "",
        address=clinic.address,
        phone=clinic.phone,
        specialty_type=clinic.specialty_type,
        logo_url=clinic.logo_url,
        services=[
            ServicePublicItem(
                id=str(s.id),
                name=s.name,
                duration_minutes=s.duration_minutes,
                price=float(s.price),
                description=s.description,
            )
            for s in services
        ],
        doctors=doctors,
    )


@router.get("/{clinic_id}/doctors", response_model=list[DoctorPublicItem])
async def list_public_doctors_by_id(
    clinic_id: UUID = Path(..., description="ID de la clínica"),
    db: AsyncSession = Depends(get_db),
):
    """Listado de doctores por ID (usado por el dashboard interno)."""
    clinic = await _get_clinic_by_id(clinic_id, db)
    return await _get_public_doctors(clinic.id, db)


@router.get("/slug/{slug}/doctors", response_model=list[DoctorPublicItem])
async def list_public_doctors_by_slug(
    slug: str = Path(..., description="Slug de la clínica"),
    db: AsyncSession = Depends(get_db),
):
    """Listado de doctores por Slug."""
    clinic = await _get_clinic_by_slug(slug, db)
    return await _get_public_doctors(clinic.id, db)


@router.get("/{slug}/availability", response_model=AvailabilityResponse)
async def public_availability(
    slug: str = Path(..., description="Slug de la clínica"),
    doctor_id: UUID = Query(..., description="ID del doctor"),
    target_date: date = Query(..., alias="date", description="Fecha (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Consulta slots disponibles de un doctor (endpoint público).
    Respeta excepciones de horario (vacaciones, etc).
    """
    clinic = await _get_clinic_by_slug(slug, db)
    
    # Usar el servicio centralizado que ya maneja overrides
    from app.services import appointment_service
    return await appointment_service.get_availability(
        db, clinic_id=clinic.id, doctor_id=doctor_id, target_date=target_date
    )


@router.post("/{slug}/book", response_model=PublicBookingResponse, status_code=201)
async def public_book_appointment(
    data: PublicBookingRequest,
    slug: str = Path(..., description="Slug de la clínica"),
    db: AsyncSession = Depends(get_db),
):
    """
    Reserva una cita desde el link público.

    Flujo:
    1. Busca al paciente por DNI en la clínica. Si no existe, lo crea.
    2. Valida disponibilidad del doctor (sin solapamiento).
    3. Crea la cita en estado `scheduled`.
    """
    clinic = await _get_clinic_by_slug(slug, db)
    clinic_id = clinic.id

    # Verificar doctor
    doctor_result = await db.execute(
        select(User).where(
            User.id == data.doctor_id,
            User.clinic_id == clinic_id,
            User.role.in_([UserRole.DOCTOR, UserRole.OBSTETRA]),
            User.is_active.is_(True),
        )
    )
    doctor = doctor_result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor")

    # Validar que end_time > start_time
    if data.end_time <= data.start_time:
        raise ValidationException("La hora de fin debe ser posterior a la de inicio")

    # Validar solapamiento
    await _check_overlap(db, data.doctor_id, data.start_time, data.end_time)

    # Buscar o crear paciente
    dni_hash = hashlib.sha256(f"{clinic_id}:{data.patient_dni}".encode()).hexdigest()

    patient_result = await db.execute(
        select(Patient).where(
            Patient.dni_hash == dni_hash,
            Patient.clinic_id == clinic_id,
        )
    )
    patient = patient_result.scalar_one_or_none()

    if not patient:
        # Crear nuevo paciente
        patient = Patient(
            clinic_id=clinic_id,
            dni=encrypt_pii(data.patient_dni),
            dni_hash=dni_hash,
            first_name=data.patient_first_name,
            last_name=data.patient_last_name,
            phone=encrypt_pii(data.patient_phone) if data.patient_phone else None,
            email=encrypt_pii(data.patient_email) if data.patient_email else None,
        )
        db.add(patient)
        await db.flush()

    # Crear cita
    appointment = Appointment(
        clinic_id=clinic_id,
        patient_id=patient.id,
        doctor_id=data.doctor_id,
        start_time=data.start_time,
        end_time=data.end_time,
        status=AppointmentStatus.SCHEDULED,
        service_type=data.service_type,
        notes=data.notes,
    )
    db.add(appointment)
    await db.flush()

    return PublicBookingResponse(
        appointment_id=appointment.id,
        patient_id=patient.id,
        status=appointment.status,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
    )
