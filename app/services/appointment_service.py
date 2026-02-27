"""
Servicio de citas: CRUD, state machine, validación de solapamiento,
cálculo de disponibilidad y reserva pública.
"""

import math
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    is_valid_transition,
)
from app.models.doctor_schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.user import User
from app.core.security import decrypt_pii
from app.schemas.appointment import (
    AppointmentBookerEmbed,
    AppointmentCreate,
    AppointmentDoctorEmbed,
    AppointmentListResponse,
    AppointmentPatientEmbed,
    AppointmentResponse,
    AppointmentStatusChange,
    AppointmentUpdate,
    AvailabilityResponse,
    TimeSlot,
)
from app.models.clinic import Clinic
from app.services.audit_service import log_action
from app.services.organization_service import get_org_clinic_ids


# ── Helpers ──────────────────────────────────────────

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


async def _get_clinic_org_id(db: AsyncSession, clinic_id: UUID) -> UUID | None:
    """Obtiene el organization_id de una clínica (None si independiente)."""
    result = await db.execute(
        select(Clinic.organization_id).where(Clinic.id == clinic_id)
    )
    return result.scalar_one_or_none()


def _appointment_to_response(appt: Appointment) -> AppointmentResponse:
    """Convierte un modelo Appointment a su schema de respuesta."""
    patient_name = None
    doctor_name = None
    clinic_name = None
    patient_embed = None
    doctor_embed = None

    if appt.patient:
        patient_name = f"{appt.patient.first_name} {appt.patient.last_name}"
        patient_embed = AppointmentPatientEmbed(
            id=appt.patient.id,
            dni=decrypt_pii(appt.patient.dni),
            first_name=appt.patient.first_name,
            last_name=appt.patient.last_name,
            phone=decrypt_pii(appt.patient.phone) if appt.patient.phone else None,
            email=decrypt_pii(appt.patient.email) if appt.patient.email else None,
        )
    if appt.doctor:
        doctor_name = f"{appt.doctor.first_name} {appt.doctor.last_name}"
        doctor_embed = AppointmentDoctorEmbed(
            id=appt.doctor.id,
            first_name=appt.doctor.first_name,
            last_name=appt.doctor.last_name,
            specialty=appt.doctor.specialty,
            cmp_number=appt.doctor.cmp_number,
        )
    if hasattr(appt, "clinic") and appt.clinic:
        clinic_name = appt.clinic.display_name

    booker_embed = None
    if hasattr(appt, "booker") and appt.booker:
        booker_embed = AppointmentBookerEmbed(
            id=appt.booker.id,
            first_name=appt.booker.first_name,
            last_name=appt.booker.last_name,
        )

    return AppointmentResponse(
        id=appt.id,
        clinic_id=appt.clinic_id,
        patient_id=appt.patient_id,
        doctor_id=appt.doctor_id,
        start_time=appt.start_time,
        end_time=appt.end_time,
        status=appt.status,
        service_type=appt.service_type,
        notes=appt.notes,
        booked_by=appt.booked_by,
        cancellation_reason=appt.cancellation_reason,
        cancelled_by=appt.cancelled_by,
        patient_name=patient_name,
        doctor_name=doctor_name,
        clinic_name=clinic_name,
        patient=patient_embed,
        doctor=doctor_embed,
        booker=booker_embed,
        created_at=appt.created_at,
        updated_at=appt.updated_at,
    )


def _load_options():
    """Opciones de carga eager para relaciones de Appointment (incluye clinic para cross-sede)."""
    return [
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor),
        joinedload(Appointment.clinic),
        joinedload(Appointment.booker),
    ]


# ── Validación de solapamiento ───────────────────────

async def _check_overlap(
    db: AsyncSession,
    doctor_id: UUID,
    start_time: datetime,
    end_time: datetime,
    exclude_id: UUID | None = None,
) -> None:
    """
    Verifica que no exista solapamiento de citas para el mismo doctor.
    Dos citas se solapan si: existing.start < new.end AND existing.end > new.start
    """
    query = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status.not_in([
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        ]),
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )

    if exclude_id:
        query = query.where(Appointment.id != exclude_id)

    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise ConflictException(
            f"El doctor ya tiene una cita entre {existing.start_time.strftime('%H:%M')} "
            f"y {existing.end_time.strftime('%H:%M')} en esa fecha"
        )


# ── CRUD ─────────────────────────────────────────────

async def create_appointment(
    db: AsyncSession,
    user: User,
    data: AppointmentCreate,
    ip_address: str | None = None,
) -> AppointmentResponse:
    """Crea una nueva cita validando solapamiento."""
    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    # Verificar que el paciente existe (cross-sede si tiene org)
    if org_id:
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == data.patient_id,
                Patient.organization_id == org_id,
            )
        )
    else:
        patient_result = await db.execute(
            select(Patient).where(
                Patient.id == data.patient_id,
                Patient.clinic_id == clinic_id,
            )
        )
    if not patient_result.scalar_one_or_none():
        raise NotFoundException("Paciente")

    # Verificar que el doctor existe y pertenece a la clínica
    doctor_result = await db.execute(
        select(User).where(
            User.id == data.doctor_id,
            User.clinic_id == clinic_id,
            User.is_active.is_(True),
        )
    )
    if not doctor_result.scalar_one_or_none():
        raise NotFoundException("Doctor")

    # Validar que no haya solapamiento
    await _check_overlap(db, data.doctor_id, data.start_time, data.end_time)

    # Crear la cita
    appointment = Appointment(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        start_time=data.start_time,
        end_time=data.end_time,
        status=AppointmentStatus.SCHEDULED,
        service_type=data.service_type,
        notes=data.notes,
        booked_by=user.id,
    )
    db.add(appointment)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="appointment",
        entity_id=str(appointment.id),
        action="create",
        new_data={
            "patient_id": str(data.patient_id),
            "doctor_id": str(data.doctor_id),
            "start_time": data.start_time.isoformat(),
            "service_type": data.service_type,
        },
        ip_address=ip_address,
    )

    # Recargar con relaciones
    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(Appointment.id == appointment.id)
    )
    appointment = result.scalar_one()

    return _appointment_to_response(appointment)


async def get_appointment(
    db: AsyncSession,
    appointment_id: UUID,
    clinic_id: UUID,
) -> AppointmentResponse:
    """Obtiene una cita por ID con datos de paciente y doctor."""
    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == clinic_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise NotFoundException("Cita")

    return _appointment_to_response(appointment)


async def list_appointments(
    db: AsyncSession,
    clinic_id: UUID,
    *,
    page: int = 1,
    size: int = 20,
    doctor_id: UUID | None = None,
    patient_id: UUID | None = None,
    status: AppointmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AppointmentListResponse:
    """Lista citas con paginación y filtros."""
    query = (
        select(Appointment)
        .options(*_load_options())
        .where(Appointment.clinic_id == clinic_id)
    )

    # Filtros
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if patient_id:
        query = query.where(Appointment.patient_id == patient_id)
    if status:
        query = query.where(Appointment.status == status)
    if date_from:
        start_dt = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
        query = query.where(Appointment.start_time >= start_dt)
    if date_to:
        end_dt = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)
        query = query.where(Appointment.start_time <= end_dt)

    # Count total
    count_query = select(func.count()).select_from(
        query.with_only_columns(Appointment.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginación y orden
    offset = (page - 1) * size
    query = query.order_by(Appointment.start_time.desc())
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    appointments = result.scalars().unique().all()

    return AppointmentListResponse(
        items=[_appointment_to_response(a) for a in appointments],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


async def update_appointment(
    db: AsyncSession,
    appointment_id: UUID,
    user: User,
    data: AppointmentUpdate,
    ip_address: str | None = None,
) -> AppointmentResponse:
    """
    Actualiza una cita existente.
    Solo se pueden actualizar citas en estado scheduled o confirmed.
    """
    clinic_id = user.clinic_id

    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == clinic_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise NotFoundException("Cita")

    # Solo permitir edición en estados no terminales
    if appointment.status in (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ):
        raise ValidationException(
            f"No se puede editar una cita en estado '{appointment.status.value}'"
        )

    # Guardar datos anteriores para audit
    old_data = {
        "start_time": appointment.start_time.isoformat(),
        "end_time": appointment.end_time.isoformat(),
        "service_type": appointment.service_type,
    }

    update_fields = data.model_dump(exclude_unset=True)
    new_data_log = {}

    # Si se cambia horario, validar solapamiento
    new_start = update_fields.get("start_time", appointment.start_time)
    new_end = update_fields.get("end_time", appointment.end_time)

    if "start_time" in update_fields or "end_time" in update_fields:
        await _check_overlap(
            db, appointment.doctor_id, new_start, new_end, exclude_id=appointment.id
        )

    for field, value in update_fields.items():
        if value is not None:
            setattr(appointment, field, value)
            new_data_log[field] = value.isoformat() if isinstance(value, datetime) else value

    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="appointment",
        entity_id=str(appointment.id),
        action="update",
        old_data=old_data,
        new_data=new_data_log,
        ip_address=ip_address,
    )

    # Recargar con relaciones
    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(Appointment.id == appointment.id)
    )
    appointment = result.scalar_one()

    return _appointment_to_response(appointment)


async def change_status(
    db: AsyncSession,
    appointment_id: UUID,
    user: User,
    data: AppointmentStatusChange,
    ip_address: str | None = None,
) -> AppointmentResponse:
    """
    Cambia el estado de una cita usando la state machine.
    Valida que la transición sea permitida.
    """
    clinic_id = user.clinic_id

    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == clinic_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise NotFoundException("Cita")

    # Validar transición con la state machine
    if not is_valid_transition(appointment.status, data.status):
        from app.models.appointment import VALID_TRANSITIONS
        valid = VALID_TRANSITIONS.get(appointment.status, [])
        raise ValidationException(
            f"No se puede cambiar de '{appointment.status.value}' a '{data.status.value}'. "
            f"Transiciones válidas: {', '.join(s.value for s in valid)}"
        )

    old_status = appointment.status.value
    appointment.status = data.status

    # Si se cancela, registrar motivo y quién canceló
    if data.status == AppointmentStatus.CANCELLED:
        appointment.cancellation_reason = data.cancellation_reason
        appointment.cancelled_by = user.id

    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="appointment",
        entity_id=str(appointment.id),
        action="status_change",
        old_data={"status": old_status},
        new_data={
            "status": data.status.value,
            "cancellation_reason": data.cancellation_reason,
        },
        ip_address=ip_address,
    )

    # Hooks al completar cita
    if data.status == AppointmentStatus.COMPLETED:
        await _generate_commission_on_complete(db, appointment)
        await _auto_deduct_supplies_on_complete(db, appointment, user.id)

    # Recargar con relaciones
    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(Appointment.id == appointment.id)
    )
    appointment = result.scalar_one()

    return _appointment_to_response(appointment)


async def _generate_commission_on_complete(
    db: AsyncSession, appointment: Appointment
) -> None:
    """Busca el servicio por nombre y genera comisión si existe regla."""
    from app.models.service import Service
    from app.services.commission_service import generate_commission_entry

    # Buscar servicio por nombre (service_type)
    svc_result = await db.execute(
        select(Service).where(
            Service.clinic_id == appointment.clinic_id,
            Service.name == appointment.service_type,
        )
    )
    service = svc_result.scalar_one_or_none()
    if not service:
        return  # Sin servicio vinculado, no se genera comisión

    await generate_commission_entry(
        db,
        clinic_id=appointment.clinic_id,
        doctor_id=appointment.doctor_id,
        appointment_id=appointment.id,
        service_id=service.id,
        patient_id=appointment.patient_id,
        service_amount=service.price,
    )


async def _auto_deduct_supplies_on_complete(
    db: AsyncSession, appointment: Appointment, user_id
) -> None:
    """Auto-descuenta insumos vinculados al servicio de la cita."""
    from app.models.service import Service
    from app.services.procedure_supply_service import auto_deduct_supplies

    svc_result = await db.execute(
        select(Service).where(
            Service.clinic_id == appointment.clinic_id,
            Service.name == appointment.service_type,
        )
    )
    service = svc_result.scalar_one_or_none()
    if not service:
        return

    await auto_deduct_supplies(
        db,
        clinic_id=appointment.clinic_id,
        service_id=service.id,
        appointment_id=appointment.id,
        user_id=user_id,
    )


# ── Citas cross-sede del paciente ────────────────────


async def list_patient_appointments_cross_sede(
    db: AsyncSession,
    user: User,
    patient_id: UUID,
    *,
    page: int = 1,
    size: int = 20,
    status: AppointmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AppointmentListResponse:
    """
    Lista citas de un paciente en TODAS las sedes de la org.
    Para clínicas independientes, solo muestra citas de la sede actual.
    Incluye clinic_name para identificar la sede de cada cita.
    """
    clinic_id = user.clinic_id
    org_id = await _get_clinic_org_id(db, clinic_id)

    query = (
        select(Appointment)
        .options(*_load_options())
        .where(Appointment.patient_id == patient_id)
    )

    if org_id:
        org_clinic_ids = await get_org_clinic_ids(db, org_id)
        query = query.where(Appointment.clinic_id.in_(org_clinic_ids))
    else:
        query = query.where(Appointment.clinic_id == clinic_id)

    if status:
        query = query.where(Appointment.status == status)
    if date_from:
        start_dt = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
        query = query.where(Appointment.start_time >= start_dt)
    if date_to:
        end_dt = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)
        query = query.where(Appointment.start_time <= end_dt)

    # Count total
    count_query = select(func.count()).select_from(
        query.with_only_columns(Appointment.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginación
    offset = (page - 1) * size
    query = query.order_by(Appointment.start_time.desc())
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    appointments = result.scalars().unique().all()

    return AppointmentListResponse(
        items=[_appointment_to_response(a) for a in appointments],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


# ── Disponibilidad y Slots ───────────────────────────

async def get_availability(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID,
    target_date: date,
) -> AvailabilityResponse:
    """
    Calcula los slots disponibles para un doctor en una fecha específica.

    1. Obtiene los horarios configurados del doctor para ese día de la semana
    2. Genera slots según la duración configurada
    3. Marca como no disponibles los que ya tienen cita
    """
    # Obtener el nombre del doctor
    doctor_result = await db.execute(
        select(User).where(User.id == doctor_id, User.clinic_id == clinic_id)
    )
    doctor = doctor_result.scalar_one_or_none()
    if not doctor:
        raise NotFoundException("Doctor")

    # 1. Verificar si hay OVERRIDES para este doctor en esta fecha (Prioridad alta)
    from app.models.staff_schedule_override import StaffScheduleOverride, OverrideType
    
    overrides_result = await db.execute(
        select(StaffScheduleOverride).where(
            StaffScheduleOverride.user_id == doctor_id,
            StaffScheduleOverride.clinic_id == clinic_id,
            StaffScheduleOverride.date_start <= target_date,
            StaffScheduleOverride.date_end >= target_date,
        )
    )
    overrides = overrides_result.scalars().all()
    
    # Si hay una excepción que bloquea el día (Vacaciones, Día Libre, Feriado)
    if any(ov.override_type in (OverrideType.VACATION, OverrideType.DAY_OFF, OverrideType.HOLIDAY) for ov in overrides):
        return AvailabilityResponse(
            doctor_id=doctor_id,
            doctor_name=f"{doctor.first_name} {doctor.last_name}",
            date=target_date,
            slots=[],
        )

    # Día de la semana (Python: 0=Lunes ... 6=Domingo)
    day_of_week = target_date.weekday()

    # 2. Determinar horarios base (Regular vs Override)
    # Si hay un cambio de turno o turno extra, eso manda.
    effective_schedules: list[tuple[time, time, int]] = []
    
    # Buscar overrides de trabajo (SHIFT_CHANGE, EXTRA_SHIFT)
    work_overrides = [
        ov for ov in overrides 
        if ov.override_type in (OverrideType.SHIFT_CHANGE, OverrideType.EXTRA_SHIFT)
    ]
    
    if work_overrides:
        # Usar los horarios de los overrides
        for ov in work_overrides:
            if ov.new_start_time and ov.new_end_time:
                # Si es un shift_change, intentamos heredar el slot_duration de un horario regular si existe
                duration = 30 # Default
                reg_sched_result = await db.execute(
                    select(DoctorSchedule.slot_duration_minutes).where(
                        DoctorSchedule.doctor_id == doctor_id,
                        DoctorSchedule.clinic_id == clinic_id,
                        DoctorSchedule.is_active.is_(True)
                    ).limit(1)
                )
                reg_duration = reg_sched_result.scalar_one_or_none()
                if reg_duration:
                    duration = reg_duration
                
                effective_schedules.append((ov.new_start_time, ov.new_end_time, duration))
    else:
        # No hay overrides de trabajo, usar horario regular
        schedules_result = await db.execute(
            select(DoctorSchedule).where(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.clinic_id == clinic_id,
                DoctorSchedule.day_of_week == day_of_week,
                DoctorSchedule.is_active.is_(True),
            )
        )
        schedules = schedules_result.scalars().all()
        for s in schedules:
            effective_schedules.append((s.start_time, s.end_time, s.slot_duration_minutes))

    if not effective_schedules:
        return AvailabilityResponse(
            doctor_id=doctor_id,
            doctor_name=f"{doctor.first_name} {doctor.last_name}",
            date=target_date,
            slots=[],
        )

    # 3. Obtener citas existentes del doctor para esa fecha
    date_start = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
    date_end = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)

    existing_result = await db.execute(
        select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= date_start,
            Appointment.start_time <= date_end,
            Appointment.status.not_in([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW,
            ]),
        )
    )
    existing_appointments = existing_result.scalars().all()

    # 4. Generar slots y marcar disponibilidad
    all_slots: list[TimeSlot] = []

    for start_t, end_t, duration in effective_schedules:
        slots = _generate_slots(
            target_date,
            start_t,
            end_t,
            duration,
            existing_appointments,
        )
        all_slots.extend(slots)

    # Ordenar por hora de inicio
    all_slots.sort(key=lambda s: s.start_time)

    return AvailabilityResponse(
        doctor_id=doctor_id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        date=target_date,
        slots=all_slots,
    )


def _generate_slots(
    target_date: date,
    sched_start: time,
    sched_end: time,
    slot_minutes: int,
    existing: list[Appointment],
) -> list[TimeSlot]:
    """Genera slots de tiempo y los marca como disponibles o no."""
    slots: list[TimeSlot] = []

    current = datetime.combine(target_date, sched_start).replace(tzinfo=timezone.utc)
    end = datetime.combine(target_date, sched_end).replace(tzinfo=timezone.utc)
    delta = timedelta(minutes=slot_minutes)

    while current + delta <= end:
        slot_start = current
        slot_end = current + delta

        # Verificar si el slot colisiona con alguna cita existente
        is_available = not any(
            appt.start_time < slot_end and appt.end_time > slot_start
            for appt in existing
        )

        # Si la fecha es hoy, marcar como no disponible slots ya pasados
        now = datetime.now(timezone.utc)
        if slot_start < now:
            is_available = False

        slots.append(TimeSlot(
            start_time=slot_start,
            end_time=slot_end,
            available=is_available,
        ))

        current += delta

    return slots


# ── Horarios de Doctor (CRUD) ────────────────────────

async def create_schedule(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID,
    day_of_week: int,
    start_time: time,
    end_time: time,
    slot_duration_minutes: int = 30,
) -> DoctorSchedule:
    """Crea un bloque de horario para un doctor."""
    # Verificar que el doctor existe
    doctor_result = await db.execute(
        select(User).where(User.id == doctor_id, User.clinic_id == clinic_id)
    )
    if not doctor_result.scalar_one_or_none():
        raise NotFoundException("Doctor")

    # Verificar superposición de horarios del mismo doctor/día
    existing_result = await db.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.day_of_week == day_of_week,
            DoctorSchedule.is_active.is_(True),
            DoctorSchedule.start_time < end_time,
            DoctorSchedule.end_time > start_time,
        )
    )
    if existing_result.scalar_one_or_none():
        raise ConflictException(
            "Ya existe un horario que se superpone para este doctor en ese día"
        )

    schedule = DoctorSchedule(
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        slot_duration_minutes=slot_duration_minutes,
    )
    db.add(schedule)
    await db.flush()

    return schedule


async def get_doctor_schedules(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID,
) -> list[DoctorSchedule]:
    """Obtiene todos los horarios activos de un doctor."""
    result = await db.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.clinic_id == clinic_id,
            DoctorSchedule.is_active.is_(True),
        ).order_by(DoctorSchedule.day_of_week, DoctorSchedule.start_time)
    )
    return list(result.scalars().all())


async def update_schedule(
    db: AsyncSession,
    schedule_id: UUID,
    clinic_id: UUID,
    *,
    start_time: time | None = None,
    end_time: time | None = None,
    slot_duration_minutes: int | None = None,
    is_active: bool | None = None,
) -> DoctorSchedule:
    """Actualiza un bloque de horario."""
    result = await db.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.id == schedule_id,
            DoctorSchedule.clinic_id == clinic_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise NotFoundException("Horario")

    if start_time is not None:
        schedule.start_time = start_time
    if end_time is not None:
        schedule.end_time = end_time
    if slot_duration_minutes is not None:
        schedule.slot_duration_minutes = slot_duration_minutes
    if is_active is not None:
        schedule.is_active = is_active

    await db.flush()
    return schedule


async def delete_schedule(
    db: AsyncSession,
    schedule_id: UUID,
    clinic_id: UUID,
) -> None:
    """Desactiva un bloque de horario (soft delete)."""
    result = await db.execute(
        select(DoctorSchedule).where(
            DoctorSchedule.id == schedule_id,
            DoctorSchedule.clinic_id == clinic_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise NotFoundException("Horario")

    schedule.is_active = False
    await db.flush()


# ── Agenda Diaria ────────────────────────────────────

async def get_daily_agenda(
    db: AsyncSession,
    clinic_id: UUID,
    doctor_id: UUID,
    target_date: date,
) -> list[AppointmentResponse]:
    """Obtiene todas las citas de un doctor para un día específico."""
    date_start = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
    date_end = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)

    result = await db.execute(
        select(Appointment)
        .options(*_load_options())
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= date_start,
            Appointment.start_time <= date_end,
        )
        .order_by(Appointment.start_time)
    )
    appointments = result.scalars().unique().all()

    return [_appointment_to_response(a) for a in appointments]
