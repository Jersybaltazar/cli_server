"""
Lógica de negocio para PatientPackage — Inscripción en paquetes y pagos parciales.
Incluye auto-generación de cronograma CPN.
"""

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, ValidationException
from app.models.accounts import AccountReceivable, AccountStatus
from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic import Clinic
from app.models.patient import Patient
from app.models.patient_package import (
    PackagePayment,
    PatientPackage,
    PatientPackageStatus,
)
from app.models.service_package import PackageItem, ServicePackage
from app.models.user import User
from app.schemas.patient_package import (
    PackageEmbed,
    PackageItemEmbed,
    PackagePaymentCreate,
    PackagePaymentResponse,
    PatientPackageEnroll,
    PatientPackageListResponse,
    PatientPackageResponse,
)


# ── Helpers ──────────────────────────────


def _payment_to_response(p: PackagePayment) -> PackagePaymentResponse:
    return PackagePaymentResponse(
        id=p.id,
        patient_package_id=p.patient_package_id,
        clinic_id=p.clinic_id,
        amount=float(p.amount),
        payment_method=p.payment_method,
        cash_movement_id=p.cash_movement_id,
        invoice_id=p.invoice_id,
        notes=p.notes,
        created_by=p.created_by,
        paid_at=p.paid_at,
        created_at=p.created_at,
    )


def _pp_to_response(pp: PatientPackage) -> PatientPackageResponse:
    pkg_embed: PackageEmbed | None = None
    if pp.package:
        pkg_embed = PackageEmbed(
            id=pp.package.id,
            name=pp.package.name,
            auto_schedule=pp.package.auto_schedule,
            items=[
                PackageItemEmbed(
                    id=item.id,
                    service_id=item.service_id,
                    quantity=item.quantity,
                    description_override=item.description_override,
                    gestational_week_target=item.gestational_week_target,
                    service_name=item.service.name if item.service else None,
                )
                for item in (pp.package.items or [])
            ],
        )

    return PatientPackageResponse(
        id=pp.id,
        clinic_id=pp.clinic_id,
        patient_id=pp.patient_id,
        package_id=pp.package_id,
        enrolled_by=pp.enrolled_by,
        total_amount=float(pp.total_amount),
        amount_paid=float(pp.amount_paid),
        balance=float(pp.balance),
        status=pp.status,
        notes=pp.notes,
        enrolled_at=pp.enrolled_at,
        completed_at=pp.completed_at,
        created_at=pp.created_at,
        updated_at=pp.updated_at,
        package_name=pp.package.name if pp.package else None,
        patient_name=pp.patient.full_name if pp.patient else None,
        package=pkg_embed,
        payments=[_payment_to_response(p) for p in pp.payments],
    )


_PP_LOAD_OPTIONS = (
    selectinload(PatientPackage.package)
    .selectinload(ServicePackage.items)
    .selectinload(PackageItem.service),
    selectinload(PatientPackage.patient),
    selectinload(PatientPackage.payments),
)


# ── ENROLL ───────────────────────────────


async def enroll_patient(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    data: PatientPackageEnroll,
) -> PatientPackageResponse:
    """Inscribe un paciente en un paquete. Opcionalmente registra pago inicial."""

    # Verificar paquete existe y está activo
    pkg_result = await db.execute(
        select(ServicePackage)
        .where(
            ServicePackage.id == data.package_id,
            ServicePackage.clinic_id == clinic_id,
            ServicePackage.is_active.is_(True),
        )
        .options(selectinload(ServicePackage.items).selectinload(PackageItem.service))
    )
    package = pkg_result.scalar_one_or_none()
    if not package:
        raise NotFoundException("Paquete")

    # Verificar paciente existe (soporte multi-sede: buscar por org si aplica)
    org_result = await db.execute(
        select(Clinic.organization_id).where(Clinic.id == clinic_id)
    )
    org_id = org_result.scalar_one_or_none()

    if org_id:
        pat_q = select(Patient).where(
            Patient.id == data.patient_id,
            Patient.organization_id == org_id,
        )
    else:
        pat_q = select(Patient).where(
            Patient.id == data.patient_id,
            Patient.clinic_id == clinic_id,
        )
    patient = (await db.execute(pat_q)).scalar_one_or_none()
    if not patient:
        raise NotFoundException("Paciente")

    # Crear inscripción
    pp = PatientPackage(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        package_id=data.package_id,
        enrolled_by=user.id,
        total_amount=package.total_price,
        amount_paid=Decimal("0.00"),
        status=PatientPackageStatus.ACTIVE,
        notes=data.notes,
    )
    db.add(pp)
    await db.flush()

    # Pago inicial si se proporcionó
    if data.initial_payment and data.initial_payment > 0:
        payment = PackagePayment(
            patient_package_id=pp.id,
            clinic_id=clinic_id,
            amount=Decimal(str(data.initial_payment)),
            payment_method=data.payment_method,
            created_by=user.id,
        )
        db.add(payment)
        pp.amount_paid = Decimal(str(data.initial_payment))

        # Auto-completar si balance = 0
        if pp.balance <= 0:
            pp.status = PatientPackageStatus.COMPLETED
            pp.completed_at = datetime.now(timezone.utc)

    # Auto-generar citas CPN si corresponde
    if package.auto_schedule and patient.fur:
        await _auto_schedule_cpn_controls(db, clinic_id, patient, package, user)

    # Crear cuenta por cobrar si queda balance pendiente
    if pp.balance > 0:
        ar = AccountReceivable(
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            description=f"Paquete: {package.name}",
            total_amount=package.total_price,
            amount_paid=pp.amount_paid,
            reference_type="package",
            reference_id=pp.id,
            status=AccountStatus.PENDING if pp.amount_paid == 0 else AccountStatus.PARTIAL,
        )
        db.add(ar)

    await db.commit()

    return await get_patient_package(db, clinic_id=clinic_id, patient_package_id=pp.id)


# ── Auto-generación de cronograma CPN (Tarea 2.3) ───


async def _auto_schedule_cpn_controls(
    db: AsyncSession,
    clinic_id: UUID,
    patient: Patient,
    package: ServicePackage,
    user: User,
) -> None:
    """
    Genera citas automáticas para controles CPN basadas en la FUR del paciente.
    Cada PackageItem con gestational_week_target genera una cita en la fecha
    correspondiente a esa semana gestacional.
    """
    fur = patient.fur
    if not fur:
        return

    for item in package.items:
        if item.gestational_week_target is None:
            continue

        # Calcular fecha objetivo: FUR + (semana_target * 7 días)
        target_date = fur + timedelta(weeks=item.gestational_week_target)

        # No agendar citas en el pasado
        if target_date < date.today():
            continue

        # Crear cita a las 09:00 como hora por defecto (será reasignada por recepción)
        start_dt = datetime(
            target_date.year, target_date.month, target_date.day,
            9, 0, tzinfo=timezone.utc
        )
        duration = item.service.duration_minutes if item.service else 30
        end_dt = start_dt + timedelta(minutes=duration)

        service_name = item.description_override or (
            item.service.name if item.service else "Control prenatal"
        )

        appointment = Appointment(
            clinic_id=clinic_id,
            patient_id=patient.id,
            doctor_id=user.id,  # Se asignará al doctor después por recepción
            start_time=start_dt,
            end_time=end_dt,
            status=AppointmentStatus.SCHEDULED,
            service_type=service_name,
            notes=f"Auto-generada por paquete CPN - Semana {item.gestational_week_target}",
            booked_by=user.id,
        )
        db.add(appointment)


# ── REGISTER PAYMENT ─────────────────────


async def register_payment(
    db: AsyncSession,
    clinic_id: UUID,
    user: User,
    patient_package_id: UUID,
    data: PackagePaymentCreate,
) -> PatientPackageResponse:
    """Registra un pago parcial o total para un paquete inscrito."""

    result = await db.execute(
        select(PatientPackage).where(
            PatientPackage.id == patient_package_id,
            PatientPackage.clinic_id == clinic_id,
        )
    )
    pp = result.scalar_one_or_none()
    if not pp:
        raise NotFoundException("Inscripción de paquete")

    if pp.status != PatientPackageStatus.ACTIVE:
        raise ValidationException(
            f"No se pueden registrar pagos en un paquete con estado '{pp.status.value}'"
        )

    amount = Decimal(str(data.amount))
    if amount > pp.balance:
        raise ValidationException(
            f"El monto ({data.amount}) excede el balance pendiente ({float(pp.balance)})"
        )

    payment = PackagePayment(
        patient_package_id=pp.id,
        clinic_id=clinic_id,
        amount=amount,
        payment_method=data.payment_method,
        cash_movement_id=data.cash_movement_id,
        invoice_id=data.invoice_id,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(payment)

    pp.amount_paid += amount

    # Auto-completar si balance = 0
    if pp.balance <= 0:
        pp.status = PatientPackageStatus.COMPLETED
        pp.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return await get_patient_package(db, clinic_id=clinic_id, patient_package_id=pp.id)


# ── GET DETAIL ───────────────────────────


async def get_patient_package(
    db: AsyncSession,
    clinic_id: UUID,
    patient_package_id: UUID,
) -> PatientPackageResponse:
    """Obtiene detalle de un paquete inscrito con pagos."""
    result = await db.execute(
        select(PatientPackage)
        .where(
            PatientPackage.id == patient_package_id,
            PatientPackage.clinic_id == clinic_id,
        )
        .options(*_PP_LOAD_OPTIONS)
    )
    pp = result.scalar_one_or_none()
    if not pp:
        raise NotFoundException("Inscripción de paquete")
    return _pp_to_response(pp)


# ── LIST (by patient or all) ────────────


async def list_patient_packages(
    db: AsyncSession,
    clinic_id: UUID,
    patient_id: UUID | None = None,
    status: PatientPackageStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> PatientPackageListResponse:
    """Lista paquetes inscritos con historial de pagos."""
    query = select(PatientPackage).where(PatientPackage.clinic_id == clinic_id)

    if patient_id:
        query = query.where(PatientPackage.patient_id == patient_id)
    if status:
        query = query.where(PatientPackage.status == status)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    # Paginar
    query = (
        query
        .options(*_PP_LOAD_OPTIONS)
        .order_by(PatientPackage.enrolled_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(query)
    pps = result.scalars().unique().all()

    return PatientPackageListResponse(
        items=[_pp_to_response(pp) for pp in pps],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
