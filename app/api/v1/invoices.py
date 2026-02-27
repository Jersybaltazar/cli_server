"""
Endpoints de facturación electrónica SUNAT.
Crear, listar, detalle, reintentar emisión y anular comprobantes.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.invoice import SunatStatus, TipoComprobante
from app.models.user import User, UserRole
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceCreateSimple,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceRetryResponse,
    InvoiceVoidRequest,
)
from app.services import invoice_service

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    data: InvoiceCreateSimple,
    request: Request,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Crea y emite un comprobante electrónico desde el frontend.
    Acepta formato simplificado (invoice_type, patient_id) y resuelve
    automáticamente los datos SUNAT del paciente.
    """
    return await invoice_service.create_invoice_simple(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


_FRONTEND_TYPE_MAP = {
    "factura": TipoComprobante.FACTURA,
    "boleta": TipoComprobante.BOLETA,
    "nota_credito": TipoComprobante.NOTA_CREDITO,
    "nota_debito": TipoComprobante.NOTA_DEBITO,
}


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filtrar por estado (pending, accepted, etc.)"),
    invoice_type: str | None = Query(None, description="Filtrar por tipo (factura, boleta, nota_credito, nota_debito)"),
    patient_id: UUID | None = Query(None, description="Filtrar por paciente"),
    search: str | None = Query(None, description="Buscar por texto"),
    sort_by: str | None = Query("created_at", description="Campo para ordenar"),
    sort_order: str | None = Query("desc", description="Orden: asc o desc"),
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST
    )),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista comprobantes de la clínica con filtros.
    Acepta filtros amigables del frontend (status, invoice_type).
    """
    # Mapear filtros del frontend
    sunat_status = None
    if status:
        try:
            sunat_status = SunatStatus(status)
        except ValueError:
            pass

    tipo_comprobante = None
    if invoice_type:
        tipo_comprobante = _FRONTEND_TYPE_MAP.get(invoice_type)

    return await invoice_service.list_invoices(
        db,
        clinic_id=user.clinic_id,
        page=page,
        size=size,
        sunat_status=sunat_status,
        tipo_comprobante=tipo_comprobante,
        patient_id=patient_id,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    user: User = Depends(require_role(
        UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST
    )),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un comprobante con su estado SUNAT e ítems."""
    return await invoice_service.get_invoice(
        db, invoice_id=invoice_id, clinic_id=user.clinic_id
    )


@router.post("/{invoice_id}/retry", response_model=InvoiceResponse)
async def retry_invoice(
    invoice_id: UUID,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Reintenta la emisión a SUNAT de un comprobante con estado
    `pending`, `queued` o `error`.
    """
    return await invoice_service.retry_emit(
        db, invoice_id=invoice_id, user=user, ip_address=_get_client_ip(request)
    )


@router.post("/{invoice_id}/void", response_model=InvoiceResponse)
async def void_invoice(
    invoice_id: UUID,
    data: InvoiceVoidRequest,
    request: Request,
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Anula un comprobante aceptado en SUNAT.
    Requiere motivo de anulación. Solo admins.
    """
    return await invoice_service.void_invoice(
        db,
        invoice_id=invoice_id,
        user=user,
        reason=data.reason,
        ip_address=_get_client_ip(request),
    )
