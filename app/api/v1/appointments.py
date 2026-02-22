"""
Endpoints de citas médicas: CRUD, cambio de estado,
disponibilidad, agenda diaria y reserva pública.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.appointment import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentStatusChange,
    AppointmentUpdate,
    AvailabilityResponse,
)
from app.services import appointment_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ── CRUD de Citas ────────────────────────────────────

@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    doctor_id: UUID | None = Query(None, description="Filtrar por doctor"),
    patient_id: UUID | None = Query(None, description="Filtrar por paciente"),
    status: AppointmentStatus | None = Query(None, description="Filtrar por estado"),
    date_from: date | None = Query(None, description="Desde fecha (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Hasta fecha (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista citas de la clínica con filtros por doctor, paciente,
    estado y rango de fechas. Paginación incluida.
    """
    return await appointment_service.list_appointments(
        db,
        clinic_id=user.clinic_id,
        page=page,
        size=size,
        doctor_id=doctor_id,
        patient_id=patient_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/agenda", response_model=list[AppointmentResponse])
async def daily_agenda(
    target_date: date = Query(..., alias="date", description="Fecha (YYYY-MM-DD)"),
    doctor_id: UUID | None = Query(None, description="Doctor (si no se envía, usa el usuario actual)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Agenda diaria de un doctor. Si no se especifica doctor_id,
    retorna la agenda del usuario autenticado (si es doctor).
    """
    effective_doctor_id = doctor_id or user.id
    return await appointment_service.get_daily_agenda(
        db,
        clinic_id=user.clinic_id,
        doctor_id=effective_doctor_id,
        target_date=target_date,
    )


@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(
    doctor_id: UUID = Query(..., description="ID del doctor"),
    target_date: date = Query(..., alias="date", description="Fecha (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Consulta los slots de tiempo disponibles para un doctor
    en una fecha específica. Basado en sus horarios configurados
    y citas existentes.
    """
    return await appointment_service.get_availability(
        db,
        clinic_id=user.clinic_id,
        doctor_id=doctor_id,
        target_date=target_date,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene el detalle de una cita por ID."""
    return await appointment_service.get_appointment(
        db, appointment_id=appointment_id, clinic_id=user.clinic_id
    )


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea una nueva cita. Valida automáticamente que no haya
    solapamiento de horario para el doctor seleccionado.
    """
    return await appointment_service.create_appointment(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Actualiza datos de una cita (horario, servicio, notas).
    Solo citas en estado scheduled o confirmed.
    """
    return await appointment_service.update_appointment(
        db,
        appointment_id=appointment_id,
        user=user,
        data=data,
        ip_address=_get_client_ip(request),
    )


@router.patch("/{appointment_id}/status", response_model=AppointmentResponse)
async def change_appointment_status(
    appointment_id: UUID,
    data: AppointmentStatusChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cambia el estado de una cita usando la state machine:

    - **scheduled** → confirmed, cancelled, no_show
    - **confirmed** → in_progress, cancelled, no_show
    - **in_progress** → completed
    - completed, cancelled, no_show → (estados terminales, sin transiciones)

    Para cancelar, opcionalmente enviar `cancellation_reason`.
    """
    return await appointment_service.change_status(
        db,
        appointment_id=appointment_id,
        user=user,
        data=data,
        ip_address=_get_client_ip(request),
    )
