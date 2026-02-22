"""
Schemas para reportes y dashboard KPIs.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Dashboard KPIs ───────────────────────────────────

class DashboardKPIs(BaseModel):
    """KPIs principales del dashboard."""
    # Citas
    appointments_today: int = 0
    appointments_pending: int = 0
    appointments_completed_today: int = 0
    no_show_rate_month: float = Field(0.0, description="Tasa de no-show del mes (%)")

    # Pacientes
    total_patients: int = 0
    new_patients_month: int = 0

    # Ingresos
    revenue_today: Decimal = Decimal("0.00")
    revenue_month: Decimal = Decimal("0.00")
    invoices_pending: int = 0

    # Periodo de referencia
    period_start: date
    period_end: date


# ── Reporte de Ingresos ─────────────────────────────

class RevenuePeriod(BaseModel):
    """Ingresos agrupados por período."""
    period: str  # "2026-01", "2026-02", etc.
    subtotal: Decimal = Decimal("0.00")
    igv: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    invoice_count: int = 0


class RevenueReportResponse(BaseModel):
    """Reporte de ingresos por período."""
    date_from: date
    date_to: date
    periods: list[RevenuePeriod]
    grand_total: Decimal = Decimal("0.00")
    grand_subtotal: Decimal = Decimal("0.00")
    grand_igv: Decimal = Decimal("0.00")
    total_invoices: int = 0


# ── Estadísticas de Citas ────────────────────────────

class AppointmentStatusCount(BaseModel):
    """Conteo de citas por estado."""
    status: str
    count: int


class AppointmentStatsResponse(BaseModel):
    """Estadísticas de citas por período."""
    date_from: date
    date_to: date
    total: int = 0
    by_status: list[AppointmentStatusCount] = []
    by_doctor: list[dict] = Field(
        default=[], description="Conteo por doctor: [{doctor_name, count}]"
    )
    by_service_type: list[dict] = Field(
        default=[], description="Conteo por servicio: [{service_type, count}]"
    )
    no_show_rate: float = Field(0.0, description="Tasa de no-show (%)")


# ── Audit Log ───────────────────────────────────────

class AuditLogItem(BaseModel):
    """Un registro individual del audit log."""
    id: UUID
    clinic_id: UUID
    user_id: UUID | None = None
    entity: str
    entity_id: str
    action: str
    old_data: dict | None = None
    new_data: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Respuesta paginada del audit log."""
    items: list[AuditLogItem]
    total: int
    page: int
    size: int
    pages: int
