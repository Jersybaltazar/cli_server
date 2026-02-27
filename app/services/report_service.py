"""
Servicio de reportes: Dashboard KPIs, ingresos por período,
estadísticas de citas.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, cast, func, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.clinic import Clinic
from app.models.invoice import Invoice, SunatStatus
from app.models.patient import Patient
from app.models.user import User
from app.models.doctor_schedule import DoctorSchedule
from app.models.service import Service
from app.schemas.report import (
    AppointmentStatsResponse,
    AppointmentStatusCount,
    ClinicComparison,
    ComparativeDashboardResponse,
    DashboardKPIs,
    DoctorProductionItem,
    DoctorProductionReport,
    DoctorShiftCount,
    DoctorShiftCountReport,
    RevenuePeriod,
    RevenueReportResponse,
)
from app.services.organization_service import get_org_clinic_ids


# ── Dashboard KPIs ───────────────────────────────────

async def _get_org_id_for_clinic(db: AsyncSession, clinic_id) -> UUID | None:
    """Obtiene el organization_id de una clínica (None si es independiente)."""
    result = await db.execute(
        select(Clinic.organization_id).where(Clinic.id == clinic_id)
    )
    return result.scalar_one_or_none()


async def get_dashboard_kpis(
    db: AsyncSession,
    clinic_id,
) -> DashboardKPIs:
    """Calcula los KPIs principales del dashboard."""
    today = date.today()
    month_start = today.replace(day=1)
    today_start = datetime.combine(today, time.min).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(today, time.max).replace(tzinfo=timezone.utc)
    month_start_dt = datetime.combine(month_start, time.min).replace(tzinfo=timezone.utc)

    # Determinar si la clínica tiene organización (multi-sede)
    org_id = await _get_org_id_for_clinic(db, clinic_id)

    # Citas de hoy (solo sede actual — las citas son por sede)
    appts_today_result = await db.execute(
        select(func.count()).where(
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= today_start,
            Appointment.start_time <= today_end,
        )
    )
    appointments_today = appts_today_result.scalar() or 0

    # Citas pendientes hoy
    appts_pending_result = await db.execute(
        select(func.count()).where(
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= today_start,
            Appointment.start_time <= today_end,
            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
        )
    )
    appointments_pending = appts_pending_result.scalar() or 0

    # Citas completadas hoy
    appts_completed_result = await db.execute(
        select(func.count()).where(
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= today_start,
            Appointment.start_time <= today_end,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    )
    appointments_completed_today = appts_completed_result.scalar() or 0

    # No-show rate del mes
    month_total_result = await db.execute(
        select(func.count()).where(
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= month_start_dt,
        )
    )
    month_total = month_total_result.scalar() or 0

    month_noshow_result = await db.execute(
        select(func.count()).where(
            Appointment.clinic_id == clinic_id,
            Appointment.start_time >= month_start_dt,
            Appointment.status == AppointmentStatus.NO_SHOW,
        )
    )
    month_noshow = month_noshow_result.scalar() or 0
    no_show_rate = round((month_noshow / month_total * 100) if month_total > 0 else 0, 1)

    # Total pacientes — cross-sede si tiene organización
    if org_id:
        patients_total_result = await db.execute(
            select(func.count(func.distinct(Patient.id))).where(
                Patient.organization_id == org_id,
                Patient.is_active.is_(True),
            )
        )
    else:
        patients_total_result = await db.execute(
            select(func.count()).where(
                Patient.clinic_id == clinic_id,
                Patient.is_active.is_(True),
            )
        )
    total_patients = patients_total_result.scalar() or 0

    # Nuevos pacientes del mes — cross-sede si tiene organización
    if org_id:
        new_patients_result = await db.execute(
            select(func.count(func.distinct(Patient.id))).where(
                Patient.organization_id == org_id,
                Patient.created_at >= month_start_dt,
            )
        )
    else:
        new_patients_result = await db.execute(
            select(func.count()).where(
                Patient.clinic_id == clinic_id,
                Patient.created_at >= month_start_dt,
            )
        )
    new_patients_month = new_patients_result.scalar() or 0

    # Ingresos hoy (solo sede actual — facturación es por sede)
    revenue_today_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0)).where(
            Invoice.clinic_id == clinic_id,
            Invoice.issued_at >= today_start,
            Invoice.issued_at <= today_end,
            Invoice.sunat_status.in_([SunatStatus.ACCEPTED, SunatStatus.EMITTED]),
        )
    )
    revenue_today = Decimal(str(revenue_today_result.scalar() or 0))

    # Ingresos del mes
    revenue_month_result = await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0)).where(
            Invoice.clinic_id == clinic_id,
            Invoice.issued_at >= month_start_dt,
            Invoice.sunat_status.in_([SunatStatus.ACCEPTED, SunatStatus.EMITTED]),
        )
    )
    revenue_month = Decimal(str(revenue_month_result.scalar() or 0))

    # Facturas pendientes
    invoices_pending_result = await db.execute(
        select(func.count()).where(
            Invoice.clinic_id == clinic_id,
            Invoice.sunat_status.in_([SunatStatus.PENDING, SunatStatus.QUEUED, SunatStatus.ERROR]),
        )
    )
    invoices_pending = invoices_pending_result.scalar() or 0

    return DashboardKPIs(
        appointments_today=appointments_today,
        appointments_pending=appointments_pending,
        appointments_completed_today=appointments_completed_today,
        no_show_rate_month=no_show_rate,
        total_patients=total_patients,
        new_patients_month=new_patients_month,
        revenue_today=revenue_today,
        revenue_month=revenue_month,
        invoices_pending=invoices_pending,
        period_start=month_start,
        period_end=today,
    )


# ── Reporte de Ingresos ─────────────────────────────

async def get_revenue_report(
    db: AsyncSession,
    clinic_id,
    date_from: date,
    date_to: date,
) -> RevenueReportResponse:
    """Reporte de ingresos agrupado por mes."""
    dt_from = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    # Agrupar por mes (YYYY-MM)
    month_expr = func.to_char(Invoice.issued_at, "YYYY-MM")

    result = await db.execute(
        select(
            month_expr.label("period"),
            func.coalesce(func.sum(Invoice.subtotal), 0).label("subtotal"),
            func.coalesce(func.sum(Invoice.igv), 0).label("igv"),
            func.coalesce(func.sum(Invoice.total), 0).label("total"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .where(
            Invoice.clinic_id == clinic_id,
            Invoice.issued_at >= dt_from,
            Invoice.issued_at <= dt_to,
            Invoice.sunat_status.in_([SunatStatus.ACCEPTED, SunatStatus.EMITTED]),
        )
        .group_by(month_expr)
        .order_by(month_expr)
    )
    rows = result.all()

    periods = []
    grand_total = Decimal("0.00")
    grand_subtotal = Decimal("0.00")
    grand_igv = Decimal("0.00")
    total_invoices = 0

    for row in rows:
        period_subtotal = Decimal(str(row.subtotal))
        period_igv = Decimal(str(row.igv))
        period_total = Decimal(str(row.total))

        periods.append(RevenuePeriod(
            period=row.period,
            subtotal=period_subtotal,
            igv=period_igv,
            total=period_total,
            invoice_count=row.invoice_count,
        ))

        grand_subtotal += period_subtotal
        grand_igv += period_igv
        grand_total += period_total
        total_invoices += row.invoice_count

    return RevenueReportResponse(
        date_from=date_from,
        date_to=date_to,
        periods=periods,
        grand_total=grand_total,
        grand_subtotal=grand_subtotal,
        grand_igv=grand_igv,
        total_invoices=total_invoices,
    )


# ── Estadísticas de Citas ────────────────────────────

async def get_appointment_stats(
    db: AsyncSession,
    clinic_id,
    date_from: date,
    date_to: date,
) -> AppointmentStatsResponse:
    """Estadísticas de citas por estado, doctor y servicio."""
    dt_from = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    base_filter = [
        Appointment.clinic_id == clinic_id,
        Appointment.start_time >= dt_from,
        Appointment.start_time <= dt_to,
    ]

    # Total
    total_result = await db.execute(
        select(func.count()).where(*base_filter)
    )
    total = total_result.scalar() or 0

    # Por estado
    status_result = await db.execute(
        select(
            cast(Appointment.status, String).label("status"),
            func.count().label("count"),
        )
        .where(*base_filter)
        .group_by(Appointment.status)
    )
    by_status = [
        AppointmentStatusCount(status=row.status, count=row.count)
        for row in status_result.all()
    ]

    # Por doctor
    doctor_result = await db.execute(
        select(
            User.first_name,
            User.last_name,
            func.count().label("count"),
        )
        .select_from(Appointment)
        .join(User, Appointment.doctor_id == User.id)
        .where(*base_filter)
        .group_by(User.first_name, User.last_name)
        .order_by(func.count().desc())
    )
    by_doctor = [
        {"doctor_name": f"{row.first_name} {row.last_name}", "count": row.count}
        for row in doctor_result.all()
    ]

    # Por servicio
    service_result = await db.execute(
        select(
            Appointment.service_type,
            func.count().label("count"),
        )
        .where(*base_filter)
        .group_by(Appointment.service_type)
        .order_by(func.count().desc())
    )
    by_service_type = [
        {"service_type": row.service_type, "count": row.count}
        for row in service_result.all()
    ]

    # No-show rate
    noshow_result = await db.execute(
        select(func.count()).where(
            *base_filter,
            Appointment.status == AppointmentStatus.NO_SHOW,
        )
    )
    noshow_count = noshow_result.scalar() or 0
    no_show_rate = round((noshow_count / total * 100) if total > 0 else 0, 1)

    return AppointmentStatsResponse(
        date_from=date_from,
        date_to=date_to,
        total=total,
        by_status=by_status,
        by_doctor=by_doctor,
        by_service_type=by_service_type,
        no_show_rate=no_show_rate,
    )


# ── Producción Médica ──────────────────────────────


async def get_doctor_production_report(
    db: AsyncSession,
    clinic_id,
    date_from: date,
    date_to: date,
) -> DoctorProductionReport:
    """Servicios por doctor con ingresos atribuidos."""
    dt_from = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    base_filter = [
        Appointment.clinic_id == clinic_id,
        Appointment.start_time >= dt_from,
        Appointment.start_time <= dt_to,
    ]

    # Citas por doctor (total y completadas)
    doctor_stats = await db.execute(
        select(
            Appointment.doctor_id,
            User.first_name,
            User.last_name,
            func.count(Appointment.id).label("total"),
            func.sum(
                case(
                    (Appointment.status == AppointmentStatus.COMPLETED, 1),
                    else_=0,
                )
            ).label("completed"),
        )
        .select_from(Appointment)
        .join(User, Appointment.doctor_id == User.id)
        .where(*base_filter)
        .group_by(Appointment.doctor_id, User.first_name, User.last_name)
        .order_by(func.count(Appointment.id).desc())
    )
    rows = doctor_stats.all()

    doctors = []
    grand_total_appts = 0
    grand_total_revenue = Decimal("0.00")

    for row in rows:
        # Desglose por servicio para este doctor
        svc_result = await db.execute(
            select(
                Appointment.service_type,
                func.count().label("count"),
            )
            .where(
                *base_filter,
                Appointment.doctor_id == row.doctor_id,
                Appointment.status == AppointmentStatus.COMPLETED,
            )
            .group_by(Appointment.service_type)
            .order_by(func.count().desc())
        )
        services_breakdown = [
            {"service_type": s.service_type, "count": s.count}
            for s in svc_result.all()
        ]

        # Ingresos: facturas vinculadas a citas del doctor (via invoice items)
        # Simplificación: contar citas completadas * precio promedio del servicio
        completed = int(row.completed or 0)

        doctors.append(DoctorProductionItem(
            doctor_id=row.doctor_id,
            doctor_name=f"{row.first_name} {row.last_name}",
            total_appointments=row.total,
            completed_appointments=completed,
            total_revenue=Decimal("0.00"),  # Se llenará con integración de invoices
            services_breakdown=services_breakdown,
        ))
        grand_total_appts += row.total

    return DoctorProductionReport(
        date_from=date_from,
        date_to=date_to,
        doctors=doctors,
        grand_total_appointments=grand_total_appts,
        grand_total_revenue=grand_total_revenue,
    )


# ── Conteo de Turnos Mensuales ─────────────────────


async def get_doctor_shift_count(
    db: AsyncSession,
    clinic_id,
    year: int,
    month: int,
) -> DoctorShiftCountReport:
    """Turnos trabajados por doctor en un mes (basado en DoctorSchedule)."""
    import calendar

    _, days_in_month = calendar.monthrange(year, month)

    # Obtener horarios activos
    result = await db.execute(
        select(DoctorSchedule)
        .where(
            DoctorSchedule.clinic_id == clinic_id,
            DoctorSchedule.is_active.is_(True),
        )
    )
    schedules = result.scalars().all()

    # Contar días del mes que coinciden con day_of_week de cada doctor
    doctor_shifts: dict[str, dict] = {}
    for sched in schedules:
        doc_id = str(sched.doctor_id)
        if doc_id not in doctor_shifts:
            doctor_shifts[doc_id] = {"doctor_id": sched.doctor_id, "count": 0}

        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            if d.weekday() == sched.day_of_week:
                doctor_shifts[doc_id]["count"] += 1

    # Obtener nombres
    doctors = []
    for info in doctor_shifts.values():
        doc_result = await db.execute(
            select(User.first_name, User.last_name).where(User.id == info["doctor_id"])
        )
        doc = doc_result.one_or_none()
        doctor_name = f"{doc.first_name} {doc.last_name}" if doc else "Desconocido"

        doctors.append(DoctorShiftCount(
            doctor_id=info["doctor_id"],
            doctor_name=doctor_name,
            total_shifts=info["count"],
        ))

    doctors.sort(key=lambda x: x.total_shifts, reverse=True)

    return DoctorShiftCountReport(
        year=year,
        month=month,
        doctors=doctors,
    )


# ── Dashboard Comparativo por Sede ────────────────


async def get_comparative_dashboard(
    db: AsyncSession,
    organization_id: UUID,
    date_from: date,
    date_to: date,
) -> ComparativeDashboardResponse:
    """Comparativa de KPIs entre sedes de una organización."""
    dt_from = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)

    # Obtener sedes de la organización
    clinic_ids = await get_org_clinic_ids(db, organization_id)
    if not clinic_ids:
        return ComparativeDashboardResponse(
            date_from=date_from, date_to=date_to, clinics=[]
        )

    # Nombres de clínicas
    clinics_result = await db.execute(
        select(Clinic.id, Clinic.name, Clinic.branch_name).where(Clinic.id.in_(clinic_ids))
    )
    clinic_info = {row.id: (row.name, row.branch_name) for row in clinics_result.all()}

    comparisons = []
    totals = ClinicComparison(
        clinic_id=organization_id,
        clinic_name="TOTAL",
    )

    for cid in clinic_ids:
        name, branch = clinic_info.get(cid, ("Desconocida", None))

        # Citas
        appts = await db.execute(
            select(
                func.count(Appointment.id).label("total"),
                func.sum(case(
                    (Appointment.status == AppointmentStatus.COMPLETED, 1), else_=0
                )).label("completed"),
                func.sum(case(
                    (Appointment.status == AppointmentStatus.NO_SHOW, 1), else_=0
                )).label("no_show"),
            ).where(
                Appointment.clinic_id == cid,
                Appointment.start_time >= dt_from,
                Appointment.start_time <= dt_to,
            )
        )
        appt_row = appts.one()
        total_appts = appt_row.total or 0
        completed_appts = int(appt_row.completed or 0)
        no_show_count = int(appt_row.no_show or 0)
        no_show_rate = round((no_show_count / total_appts * 100) if total_appts > 0 else 0, 1)

        # Pacientes
        patients_total = await db.scalar(
            select(func.count()).where(
                Patient.clinic_id == cid, Patient.is_active.is_(True)
            )
        ) or 0

        new_patients = await db.scalar(
            select(func.count()).where(
                Patient.clinic_id == cid,
                Patient.created_at >= dt_from,
                Patient.created_at <= dt_to,
            )
        ) or 0

        # Ingresos
        revenue_result = await db.execute(
            select(
                func.coalesce(func.sum(Invoice.total), 0).label("revenue"),
                func.count(Invoice.id).label("count"),
            ).where(
                Invoice.clinic_id == cid,
                Invoice.issued_at >= dt_from,
                Invoice.issued_at <= dt_to,
                Invoice.sunat_status.in_([SunatStatus.ACCEPTED, SunatStatus.EMITTED]),
            )
        )
        rev_row = revenue_result.one()
        revenue = Decimal(str(rev_row.revenue or 0))
        invoice_count = rev_row.count or 0

        comp = ClinicComparison(
            clinic_id=cid,
            clinic_name=name,
            branch_name=branch,
            total_appointments=total_appts,
            completed_appointments=completed_appts,
            total_patients=patients_total,
            new_patients=new_patients,
            revenue=revenue,
            invoice_count=invoice_count,
            no_show_rate=no_show_rate,
        )
        comparisons.append(comp)

        # Acumular totales
        totals.total_appointments += total_appts
        totals.completed_appointments += completed_appts
        totals.total_patients += patients_total
        totals.new_patients += new_patients
        totals.revenue += revenue
        totals.invoice_count += invoice_count

    # No-show rate total
    if totals.total_appointments > 0:
        total_noshow = sum(
            c.no_show_rate * c.total_appointments / 100 for c in comparisons
        )
        totals.no_show_rate = round(total_noshow / totals.total_appointments * 100, 1)

    return ComparativeDashboardResponse(
        date_from=date_from,
        date_to=date_to,
        clinics=comparisons,
        totals=totals,
    )
