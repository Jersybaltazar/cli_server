"""
Endpoints de reportes y dashboard KPIs.
Solo accesible por admins y doctores.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.core.exceptions import ForbiddenException, ValidationException
from app.schemas.report import (
    AppointmentStatsResponse,
    AuditLogResponse,
    ComparativeDashboardResponse,
    DashboardKPIs,
    DoctorProductionReport,
    DoctorShiftCountReport,
    RevenueReportResponse,
)
from app.services import audit_service, report_service

router = APIRouter()


@router.get("/dashboard", response_model=DashboardKPIs)
async def get_dashboard(
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    KPIs principales del dashboard:
    citas del día, ingresos del mes, pacientes nuevos, tasa de no-show.
    """
    return await report_service.get_dashboard_kpis(
        db, clinic_id=user.clinic_id
    )


@router.get("/revenue", response_model=RevenueReportResponse)
async def get_revenue_report(
    date_from: date = Query(
        default=None,
        description="Desde (YYYY-MM-DD). Por defecto: inicio del mes actual",
    ),
    date_to: date = Query(
        default=None,
        description="Hasta (YYYY-MM-DD). Por defecto: hoy",
    ),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Reporte de ingresos agrupado por mes.
    Por defecto muestra los últimos 6 meses.
    """
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = (today - timedelta(days=180)).replace(day=1)

    return await report_service.get_revenue_report(
        db, clinic_id=user.clinic_id, date_from=date_from, date_to=date_to
    )


@router.get("/appointments", response_model=AppointmentStatsResponse)
async def get_appointment_stats(
    date_from: date = Query(
        default=None,
        description="Desde (YYYY-MM-DD). Por defecto: inicio del mes actual",
    ),
    date_to: date = Query(
        default=None,
        description="Hasta (YYYY-MM-DD). Por defecto: hoy",
    ),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Estadísticas de citas: total, por estado, por doctor,
    por tipo de servicio, tasa de no-show.
    """
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = today.replace(day=1)

    return await report_service.get_appointment_stats(
        db, clinic_id=user.clinic_id, date_from=date_from, date_to=date_to
    )


@router.get("/doctor-production", response_model=DoctorProductionReport)
async def get_doctor_production(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
):
    """Reporte de producción médica: servicios por doctor con ingresos."""
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = today.replace(day=1)
    return await report_service.get_doctor_production_report(
        db, clinic_id=user.clinic_id, date_from=date_from, date_to=date_to
    )


@router.get("/doctor-shifts", response_model=DoctorShiftCountReport)
async def get_doctor_shifts(
    year: int = Query(..., ge=2020, le=2050),
    month: int = Query(..., ge=1, le=12),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
):
    """Conteo de turnos mensuales por doctor."""
    return await report_service.get_doctor_shift_count(
        db, clinic_id=user.clinic_id, year=year, month=month
    )


@router.get("/comparative-dashboard", response_model=ComparativeDashboardResponse)
async def get_comparative_dashboard(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard comparativo entre sedes de la organización.
    Solo ORG_ADMIN y SUPER_ADMIN.
    """
    from app.services.report_service import _get_org_id_for_clinic

    org_id = await _get_org_id_for_clinic(db, user.clinic_id)
    if not org_id:
        raise ValidationException("La clínica no pertenece a una organización multi-sede")

    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = today.replace(day=1)

    return await report_service.get_comparative_dashboard(
        db, organization_id=org_id, date_from=date_from, date_to=date_to
    )


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    page: int = Query(default=1, ge=1, description="Número de página"),
    size: int = Query(default=15, ge=1, le=100, description="Registros por página"),
    action: str | None = Query(default=None, description="Filtrar por acción"),
    entity: str | None = Query(default=None, description="Filtrar por entidad"),
    search: str | None = Query(default=None, description="Buscar por texto"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Registro de auditoría paginado — consulta los eventos de la clínica.
    Solo accesible por administradores.
    """
    return await audit_service.get_audit_logs(
        db,
        clinic_id=user.clinic_id,
        page=page,
        size=size,
        action=action,
        entity=entity,
        search=search,
    )
