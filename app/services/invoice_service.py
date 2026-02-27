"""
Servicio de facturación: CRUD, cálculo de montos, emisión SUNAT y anulación.
"""

import math
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import (
    NotFoundException,
    ValidationException,
)
from app.models.invoice import (
    FormaPago,
    Invoice,
    InvoiceItem,
    SunatStatus,
    TipoComprobante,
)
from app.models.patient import Patient
from app.models.user import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceCreateSimple,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
)
from app.models.clinic import Clinic
from app.services.patient_service import decrypt_pii
from app.services.audit_service import log_action
from app.services.organization_service import get_org_clinic_ids
from app.services.sunat_service import (
    NubefactError,
    build_nubefact_payload,
    build_void_payload,
    emit_to_nubefact,
    get_clinic_nubefact_token,
    parse_nubefact_response,
    void_in_nubefact,
    IGV_RATE,
)


# ── Helpers ──────────────────────────────────────────

def _round2(value: Decimal) -> Decimal:
    """Redondea a 2 decimales."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_TIPO_TO_FRONTEND = {
    TipoComprobante.FACTURA: "factura",
    TipoComprobante.BOLETA: "boleta",
    TipoComprobante.NOTA_CREDITO: "nota_credito",
    TipoComprobante.NOTA_DEBITO: "nota_debito",
}


def _invoice_to_response(invoice: Invoice) -> InvoiceResponse:
    """Convierte un modelo Invoice a su schema de respuesta."""
    from app.schemas.invoice import InvoiceRefEmbed, PatientEmbed

    # Construir datos de referencia para NC/ND
    ref_embed = None
    if invoice.referenced_invoice:
        ref_embed = InvoiceRefEmbed(
            id=invoice.referenced_invoice.id,
            serie=invoice.referenced_invoice.serie,
            correlativo=invoice.referenced_invoice.correlativo,
            numero_comprobante=invoice.referenced_invoice.numero_comprobante,
            tipo_comprobante=invoice.referenced_invoice.tipo_comprobante,
            total=invoice.referenced_invoice.total,
        )

    # Construir embed del paciente si está cargado
    patient_embed = None
    patient_name = None
    if invoice.patient_id and invoice.patient:
        p = invoice.patient
        patient_embed = PatientEmbed(
            id=p.id,
            first_name=p.first_name,
            last_name=p.last_name,
            document_number=invoice.cliente_numero_doc,
        )
        patient_name = f"{p.first_name} {p.last_name}"

    # Campos amigables según tipo de comprobante
    ruc_client = None
    razon_social = None
    if invoice.cliente_tipo_doc == "6":
        # Factura → RUC
        ruc_client = invoice.cliente_numero_doc
        razon_social = invoice.cliente_denominacion
    else:
        # Boleta → si no hay patient_name, usar denominación
        if not patient_name:
            patient_name = invoice.cliente_denominacion

    return InvoiceResponse(
        id=invoice.id,
        clinic_id=invoice.clinic_id,
        patient_id=invoice.patient_id,
        appointment_id=invoice.appointment_id,
        created_by=invoice.created_by,
        tipo_comprobante=invoice.tipo_comprobante,
        serie=invoice.serie,
        correlativo=invoice.correlativo,
        numero_comprobante=invoice.numero_comprobante,
        cliente_tipo_doc=invoice.cliente_tipo_doc,
        cliente_numero_doc=invoice.cliente_numero_doc,
        cliente_denominacion=invoice.cliente_denominacion,
        cliente_direccion=invoice.cliente_direccion,
        moneda=invoice.moneda,
        subtotal=invoice.subtotal,
        igv=invoice.igv,
        total=invoice.total,
        forma_pago=invoice.forma_pago,
        sunat_status=invoice.sunat_status,
        sunat_error_message=invoice.sunat_error_message,
        pdf_url=invoice.pdf_url,
        xml_url=invoice.xml_url,
        cdr_url=invoice.cdr_url,
        notes=invoice.notes,
        voided_reason=invoice.voided_reason,
        voided_at=invoice.voided_at,
        items=[
            InvoiceItemResponse(
                id=item.id,
                description=item.description,
                quantity=item.quantity,
                unit_code=item.unit_code,
                unit_price=item.unit_price,
                igv_amount=item.igv_amount,
                total=item.total,
                service_type=item.description.split(" - ")[0] if " - " in item.description else item.description,
                subtotal=_round2(item.unit_price * item.quantity),
            )
            for item in (invoice.items or [])
        ],
        issued_at=invoice.issued_at,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        # Campos NC/ND
        referenced_invoice_id=invoice.referenced_invoice_id,
        motivo_nota=invoice.motivo_nota,
        referenced_invoice=ref_embed,
        # Paciente embebido
        patient=patient_embed,
        # Campos amigables para el frontend
        invoice_type=_TIPO_TO_FRONTEND.get(invoice.tipo_comprobante, "boleta"),
        status=invoice.sunat_status.value,
        ruc_client=ruc_client,
        razon_social=razon_social,
        patient_name=patient_name,
    )


async def _next_correlativo(
    db: AsyncSession,
    clinic_id: UUID,
    serie: str,
) -> int:
    """Obtiene el siguiente correlativo para una serie."""
    result = await db.execute(
        select(func.max(Invoice.correlativo)).where(
            Invoice.clinic_id == clinic_id,
            Invoice.serie == serie,
        )
    )
    max_corr = result.scalar()
    return (max_corr or 0) + 1


def _get_serie(tipo: TipoComprobante) -> str:
    """Retorna la serie por defecto según tipo de comprobante."""
    if tipo == TipoComprobante.FACTURA:
        return "F001"
    elif tipo == TipoComprobante.BOLETA:
        return "B001"
    elif tipo == TipoComprobante.NOTA_CREDITO:
        return "FC01"
    else:
        return "FD01"


# ── Crear factura ────────────────────────────────────

async def create_invoice(
    db: AsyncSession,
    user: User,
    data: InvoiceCreate,
    ip_address: str | None = None,
    emit_now: bool | None = None,
) -> InvoiceResponse:
    """
    Crea una factura/boleta, calcula montos y opcionalmente emite a SUNAT.
    """
    clinic_id = user.clinic_id
    serie = _get_serie(data.tipo_comprobante)
    correlativo = await _next_correlativo(db, clinic_id, serie)

    # Calcular montos por ítem y totales
    subtotal = Decimal("0.00")
    items_models: list[InvoiceItem] = []

    for item_data in data.items:
        item_subtotal = _round2(item_data.unit_price * item_data.quantity)
        item_igv = _round2(item_subtotal * IGV_RATE)
        item_total = _round2(item_subtotal + item_igv)
        subtotal += item_subtotal

        items_models.append(InvoiceItem(
            description=item_data.description,
            quantity=item_data.quantity,
            unit_code=item_data.unit_code,
            unit_price=item_data.unit_price,
            igv_amount=item_igv,
            total=item_total,
        ))

    igv_total = _round2(subtotal * IGV_RATE)
    total = _round2(subtotal + igv_total)

    # Crear invoice
    invoice = Invoice(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        appointment_id=data.appointment_id,
        created_by=user.id,
        tipo_comprobante=data.tipo_comprobante,
        serie=serie,
        correlativo=correlativo,
        cliente_tipo_doc=data.cliente_tipo_doc,
        cliente_numero_doc=data.cliente_numero_doc,
        cliente_denominacion=data.cliente_denominacion,
        cliente_direccion=data.cliente_direccion,
        moneda=data.moneda,
        subtotal=subtotal,
        igv=igv_total,
        total=total,
        forma_pago=data.forma_pago,
        sunat_status=SunatStatus.PENDING,
        notes=data.notes,
        issued_at=datetime.now(timezone.utc),
    )
    db.add(invoice)
    await db.flush()

    # Agregar ítems
    for item_model in items_models:
        item_model.invoice_id = invoice.id
        db.add(item_model)
    await db.flush()

    # Audit log
    await log_action(
        db,
        clinic_id=clinic_id,
        user_id=user.id,
        entity="invoice",
        entity_id=str(invoice.id),
        action="create",
        new_data={
            "numero_comprobante": invoice.numero_comprobante,
            "total": str(total),
            "cliente": data.cliente_denominacion,
        },
        ip_address=ip_address,
    )

    # Emitir a SUNAT si se solicita
    should_emit = emit_now if emit_now is not None else data.emit_now
    if should_emit:
        await _emit_invoice(db, invoice, user, ip_address)

    # Recargar con items y paciente
    result = await db.execute(
        select(Invoice)
        .options(
            joinedload(Invoice.items),
            joinedload(Invoice.referenced_invoice),
            joinedload(Invoice.patient),
        )
        .where(Invoice.id == invoice.id)
    )
    invoice = result.unique().scalar_one()

    return _invoice_to_response(invoice)


# ── Emitir a SUNAT ───────────────────────────────────

async def _emit_invoice(
    db: AsyncSession,
    invoice: Invoice,
    user: User,
    ip_address: str | None = None,
) -> None:
    """Intenta emitir el comprobante a NubeFact/SUNAT usando el token de la clínica."""
    try:
        # Obtener token NubeFact de la clínica (o fallback global)
        token = await get_clinic_nubefact_token(db, invoice.clinic_id)
        payload = build_nubefact_payload(invoice)
        response_data = await emit_to_nubefact(payload, token=token)

        status, error_msg = parse_nubefact_response(response_data)
        invoice.sunat_status = status
        invoice.nubefact_response = response_data
        invoice.sunat_error_message = error_msg
        invoice.pdf_url = response_data.get("enlace_del_pdf")
        invoice.xml_url = response_data.get("enlace_del_xml")
        invoice.cdr_url = response_data.get("enlace_del_cdr")

        await db.flush()

        await log_action(
            db,
            clinic_id=invoice.clinic_id,
            user_id=user.id,
            entity="invoice",
            entity_id=str(invoice.id),
            action="emit_sunat",
            new_data={"sunat_status": status.value},
            ip_address=ip_address,
        )

    except NubefactError as e:
        invoice.sunat_status = SunatStatus.ERROR
        invoice.sunat_error_message = e.message
        invoice.nubefact_response = e.response_data
        await db.flush()


# ── Reintentar emisión ───────────────────────────────

async def retry_emit(
    db: AsyncSession,
    invoice_id: UUID,
    user: User,
    ip_address: str | None = None,
) -> InvoiceResponse:
    """Reintenta la emisión de un comprobante fallido."""
    result = await db.execute(
        select(Invoice)
        .options(
            joinedload(Invoice.items),
            joinedload(Invoice.referenced_invoice),
            joinedload(Invoice.patient),
        )
        .where(Invoice.id == invoice_id, Invoice.clinic_id == user.clinic_id)
    )
    invoice = result.unique().scalar_one_or_none()

    if not invoice:
        raise NotFoundException("Comprobante")

    if invoice.sunat_status not in (SunatStatus.PENDING, SunatStatus.ERROR, SunatStatus.QUEUED):
        raise ValidationException(
            f"Solo se pueden reintentar comprobantes pendientes o con error. Estado actual: {invoice.sunat_status.value}"
        )

    await _emit_invoice(db, invoice, user, ip_address)

    return _invoice_to_response(invoice)


# ── Anular comprobante ───────────────────────────────

async def void_invoice(
    db: AsyncSession,
    invoice_id: UUID,
    user: User,
    reason: str,
    ip_address: str | None = None,
) -> InvoiceResponse:
    """Anula un comprobante emitido en SUNAT."""
    result = await db.execute(
        select(Invoice)
        .options(
            joinedload(Invoice.items),
            joinedload(Invoice.referenced_invoice),
            joinedload(Invoice.patient),
        )
        .where(Invoice.id == invoice_id, Invoice.clinic_id == user.clinic_id)
    )
    invoice = result.unique().scalar_one_or_none()

    if not invoice:
        raise NotFoundException("Comprobante")

    if invoice.sunat_status == SunatStatus.VOIDED:
        raise ValidationException("El comprobante ya está anulado")

    if invoice.sunat_status not in (SunatStatus.ACCEPTED, SunatStatus.EMITTED):
        raise ValidationException(
            f"Solo se pueden anular comprobantes aceptados. Estado actual: {invoice.sunat_status.value}"
        )

    try:
        token = await get_clinic_nubefact_token(db, invoice.clinic_id)
        payload = build_void_payload(invoice, reason)
        response_data = await void_in_nubefact(payload, token=token)

        invoice.sunat_status = SunatStatus.VOIDED
        invoice.voided_reason = reason
        invoice.voided_at = datetime.now(timezone.utc)
        invoice.nubefact_response = response_data
        await db.flush()

    except NubefactError as e:
        invoice.sunat_error_message = f"Error al anular: {e.message}"
        await db.flush()
        raise ValidationException(f"Error al anular en SUNAT: {e.message}")

    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="invoice",
        entity_id=str(invoice.id),
        action="void",
        new_data={"reason": reason},
        ip_address=ip_address,
    )

    return _invoice_to_response(invoice)


# ── Crear desde frontend (formato simplificado) ─────

_INVOICE_TYPE_MAP = {
    "factura": TipoComprobante.FACTURA,
    "boleta": TipoComprobante.BOLETA,
    "nota_credito": TipoComprobante.NOTA_CREDITO,
    "nota_debito": TipoComprobante.NOTA_DEBITO,
}


async def create_invoice_simple(
    db: AsyncSession,
    user: User,
    data: InvoiceCreateSimple,
    ip_address: str | None = None,
) -> InvoiceResponse:
    """
    Crea un comprobante desde el formato simplificado del frontend.
    Resuelve datos del paciente y mapea invoice_type → tipo_comprobante.
    """
    # Resolver tipo de comprobante SUNAT
    tipo = _INVOICE_TYPE_MAP.get(data.invoice_type)
    if not tipo:
        raise ValidationException(f"Tipo de comprobante inválido: {data.invoice_type}")

    # Determinar datos del cliente según tipo de comprobante
    patient = None

    # Helper: buscar paciente con soporte cross-sede
    async def _find_patient(patient_id: UUID) -> Patient | None:
        # Verificar si la clínica pertenece a una organización
        clinic_result = await db.execute(
            select(Clinic.organization_id).where(Clinic.id == user.clinic_id)
        )
        org_id = clinic_result.scalar_one_or_none()

        if org_id:
            # Cross-sede: buscar en cualquier sede de la org
            org_clinic_ids = await get_org_clinic_ids(db, org_id)
            stmt = select(Patient).where(
                Patient.id == patient_id,
                Patient.clinic_id.in_(org_clinic_ids),
            )
        else:
            # Clínica independiente: solo su sede
            stmt = select(Patient).where(
                Patient.id == patient_id,
                Patient.clinic_id == user.clinic_id,
            )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    if data.invoice_type == "factura":
        # Factura: usa datos de RUC (paciente opcional)
        cliente_tipo_doc = "6"
        cliente_numero_doc = data.ruc_client
        cliente_denominacion = data.razon_social
        cliente_direccion = data.direccion_cliente

        # Si viene patient_id, resolver para referencia
        if data.patient_id:
            patient = await _find_patient(data.patient_id)
    else:
        # Boleta / NC / ND: requiere paciente, usa DNI
        patient = await _find_patient(data.patient_id)
        if not patient:
            raise NotFoundException("Paciente")

        dni = decrypt_pii(patient.dni) if patient.dni else "00000000"
        cliente_tipo_doc = "1"
        cliente_numero_doc = dni
        cliente_denominacion = f"{patient.first_name} {patient.last_name}"
        cliente_direccion = None

    # Transformar items
    items_create = [
        InvoiceItemCreate(
            description=f"{item.service_type} - {item.description}",
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        for item in data.items
    ]

    # Construir InvoiceCreate estándar
    invoice_data = InvoiceCreate(
        patient_id=data.patient_id,
        tipo_comprobante=tipo,
        cliente_tipo_doc=cliente_tipo_doc,
        cliente_numero_doc=cliente_numero_doc,
        cliente_denominacion=cliente_denominacion,
        cliente_direccion=cliente_direccion,
        items=items_create,
        notes=data.notes,
        referenced_invoice_id=data.referenced_invoice_id,
        motivo_nota=data.motivo_nota,
    )

    return await create_invoice(db, user=user, data=invoice_data, ip_address=ip_address, emit_now=False)


# ── Consultas ────────────────────────────────────────

async def get_invoice(
    db: AsyncSession,
    invoice_id: UUID,
    clinic_id: UUID,
) -> InvoiceResponse:
    """Obtiene un comprobante por ID."""
    result = await db.execute(
        select(Invoice)
        .options(
            joinedload(Invoice.items),
            joinedload(Invoice.referenced_invoice),
            joinedload(Invoice.patient),
        )
        .where(Invoice.id == invoice_id, Invoice.clinic_id == clinic_id)
    )
    invoice = result.unique().scalar_one_or_none()

    if not invoice:
        raise NotFoundException("Comprobante")

    return _invoice_to_response(invoice)


async def list_invoices(
    db: AsyncSession,
    clinic_id: UUID,
    *,
    page: int = 1,
    size: int = 20,
    sunat_status: SunatStatus | None = None,
    tipo_comprobante: TipoComprobante | None = None,
    patient_id: UUID | None = None,
) -> InvoiceListResponse:
    """Lista comprobantes con paginación y filtros."""
    query = (
        select(Invoice)
        .options(
            joinedload(Invoice.items),
            joinedload(Invoice.referenced_invoice),
            joinedload(Invoice.patient),
        )
        .where(Invoice.clinic_id == clinic_id)
    )

    if sunat_status:
        query = query.where(Invoice.sunat_status == sunat_status)
    if tipo_comprobante:
        query = query.where(Invoice.tipo_comprobante == tipo_comprobante)
    if patient_id:
        query = query.where(Invoice.patient_id == patient_id)

    # Count
    count_query = select(func.count()).select_from(
        query.with_only_columns(Invoice.id).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginación
    offset = (page - 1) * size
    query = query.order_by(Invoice.created_at.desc())
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    invoices = result.scalars().unique().all()

    return InvoiceListResponse(
        items=[_invoice_to_response(i) for i in invoices],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )
