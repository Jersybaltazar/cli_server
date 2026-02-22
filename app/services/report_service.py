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
from app.schemas.report import (
    AppointmentStatsResponse,
    AppointmentStatusCount,
    DashboardKPIs,
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
