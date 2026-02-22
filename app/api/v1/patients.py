"""
Endpoints CRUD de pacientes.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.appointment import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import AppointmentListResponse
from app.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)
from app.services import appointment_service, patient_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(20, ge=1, le=100, description="Tamaño de página"),
    search: str | None = Query(None, description="Buscar por nombre o apellido"),
    is_active: bool | None = Query(None, description="Filtrar por estado"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista pacientes de la clínica con paginación y búsqueda.
    Todos los roles pueden listar pacientes.
    """
    return await patient_service.list_patients(
        db,
        clinic_id=user.clinic_id,
        page=page,
        size=size,
        search=search,
        is_active=is_active,
    )


@router.get("/search", response_model=PatientResponse | None)
async def search_by_dni(
    dni: str = Query(..., min_length=8, description="DNI del paciente"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Busca un paciente por DNI en la clínica actual.
    Retorna null si no existe.
    """
    return await patient_service.search_by_dni(
        db, clinic_id=user.clinic_id, dni=dni
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene el detalle de un paciente por ID."""
    return await patient_service.get_patient(
        db, patient_id=patient_id, clinic_id=user.clinic_id
    )


@router.post("", response_model=PatientResponse, status_code=201)
async def create_patient(
    data: PatientCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un nuevo paciente en la clínica.
    El DNI y campos sensibles se cifran automáticamente.
    """
    return await patient_service.create_patient(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    data: PatientUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza un paciente existente.
    Solo se actualizan los campos enviados.
    """
    return await patient_service.update_patient(
        db,
        patient_id=patient_id,
        user=user,
        data=data,
        ip_address=_get_client_ip(request),
    )


@router.get("/{patient_id}/appointments", response_model=AppointmentListResponse)
async def list_patient_appointments(
    patient_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: AppointmentStatus | None = Query(None, description="Filtrar por estado"),
    date_from: date | None = Query(None, description="Desde fecha"),
    date_to: date | None = Query(None, description="Hasta fecha"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista citas del paciente en todas las sedes de la organización.
    Incluye clinic_name para identificar la sede de cada cita.
    Para clínicas independientes, solo muestra citas de la sede actual.
    """
    return await appointment_service.list_patient_appointments_cross_sede(
        db,
        user=user,
        patient_id=patient_id,
        page=page,
        size=size,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
