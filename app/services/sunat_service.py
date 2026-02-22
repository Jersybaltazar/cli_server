"""
Servicio de integración con NubeFact API para facturación SUNAT.

NubeFact es un OSE (Operador de Servicios Electrónicos) autorizado
por SUNAT para emitir comprobantes electrónicos.

Multi-tenant: cada clínica usa su propio token NubeFact almacenado
en clinic.settings["billing"]["nubefact_token"].
Docs: https://www.nubefact.com/documentacion
"""

import logging
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.clinic import Clinic
from app.models.invoice import Invoice, SunatStatus, TipoComprobante

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Constantes NubeFact ──────────────────────────────
IGV_RATE = Decimal("0.18")
TIPO_OPERACION = "0101"  # Venta interna
TIPO_IGV = 1  # Gravada - operación onerosa


class NubefactError(Exception):
    """Error de comunicación con NubeFact."""

    def __init__(self, message: str, response_data: dict | None = None):
        self.message = message
        self.response_data = response_data or {}
        super().__init__(message)


# ── Obtener token por clínica ────────────────────────

async def get_clinic_nubefact_token(
    db: AsyncSession,
    clinic_id: UUID,
) -> str | None:
    """
    Obtiene el token NubeFact de la clínica desde clinic.settings.
    Fallback al token global (.env) si la clínica no tiene uno configurado.
    """
    result = await db.execute(
        select(Clinic.settings).where(Clinic.id == clinic_id)
    )
    clinic_settings = result.scalar_one_or_none()

    if clinic_settings and isinstance(clinic_settings, dict):
        billing = clinic_settings.get("billing", {})
        token = billing.get("nubefact_token")
        if token:
            return token

    # Fallback: token global del .env (para desarrollo/clínicas sin config)
    return settings.NUBEFACT_API_TOKEN


async def get_clinic_billing_config(
    db: AsyncSession,
    clinic_id: UUID,
) -> dict:
    """
    Retorna la configuración de billing completa de la clínica.
    """
    result = await db.execute(
        select(Clinic.settings).where(Clinic.id == clinic_id)
    )
    clinic_settings = result.scalar_one_or_none()

    if clinic_settings and isinstance(clinic_settings, dict):
        return clinic_settings.get("billing", {})

    return {}


# ── Payload builders ─────────────────────────────────

def build_nubefact_payload(invoice: Invoice) -> dict:
    """
    Construye el payload JSON para NubeFact API
    a partir de un modelo Invoice con sus items.
    """
    items_payload = []
    for item in invoice.items:
        items_payload.append({
            "unidad_de_medida": item.unit_code,
            "codigo": "",
            "descripcion": item.description,
            "cantidad": item.quantity,
            "valor_unitario": float(item.unit_price),
            "precio_unitario": float(item.unit_price * (1 + IGV_RATE)),
            "subtotal": float(item.unit_price * item.quantity),
            "tipo_de_igv": TIPO_IGV,
            "igv": float(item.igv_amount),
            "total": float(item.total),
            "anticipo_regularizacion": False,
        })

    # Tipo de comprobante NubeFact: 1=Factura, 2=Boleta
    tipo_nubefact = 1 if invoice.tipo_comprobante == TipoComprobante.FACTURA else 2

    payload = {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": tipo_nubefact,
        "serie": invoice.serie,
        "numero": invoice.correlativo,
        "sunat_transaction": TIPO_OPERACION,
        "cliente_tipo_de_documento": invoice.cliente_tipo_doc,
        "cliente_numero_de_documento": invoice.cliente_numero_doc,
        "cliente_denominacion": invoice.cliente_denominacion,
        "cliente_direccion": invoice.cliente_direccion or "",
        "fecha_de_emision": invoice.issued_at.strftime("%d-%m-%Y") if invoice.issued_at else "",
        "moneda": 1 if invoice.moneda == "PEN" else 2,
        "tipo_de_cambio": "",
        "porcentaje_de_igv": float(IGV_RATE * 100),
        "total_gravada": float(invoice.subtotal),
        "total_igv": float(invoice.igv),
        "total": float(invoice.total),
        "detraccion": False,
        "forma_de_pago": invoice.forma_pago.value,
        "observaciones": invoice.notes or "",
        "items": items_payload,
    }

    return payload


def build_void_payload(invoice: Invoice, reason: str) -> dict:
    """Construye el payload para anular un comprobante en NubeFact."""
    tipo_nubefact = 1 if invoice.tipo_comprobante == TipoComprobante.FACTURA else 2

    return {
        "operacion": "generar_anulacion",
        "tipo_de_comprobante": tipo_nubefact,
        "serie": invoice.serie,
        "numero": invoice.correlativo,
        "motivo": reason,
    }


# ── Emisión ──────────────────────────────────────────

async def emit_to_nubefact(payload: dict, *, token: str | None = None) -> dict:
    """
    Envía un comprobante a NubeFact API.
    Usa el token proporcionado (por clínica) o el global como fallback.
    """
    url = settings.NUBEFACT_API_URL
    api_token = token or settings.NUBEFACT_API_TOKEN

    if not api_token or api_token == "your-nubefact-token":
        logger.warning("NubeFact token no configurado — simulando emisión")
        return {
            "aceptada_por_sunat": True,
            "sunat_description": "SIMULADO — Token no configurado",
            "enlace_del_pdf": "",
            "enlace_del_xml": "",
            "enlace_del_cdr": "",
            "cadena_para_codigo_qr": "",
        }

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"NubeFact respuesta exitosa: {data.get('sunat_description', '')}")
                return data
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("errors", str(response.text))
                logger.error(f"NubeFact error {response.status_code}: {error_msg}")
                raise NubefactError(
                    f"Error NubeFact ({response.status_code}): {error_msg}",
                    response_data=error_data,
                )

    except httpx.TimeoutException:
        logger.error("NubeFact timeout — la emisión se reintentará")
        raise NubefactError("Timeout al comunicar con NubeFact")
    except httpx.RequestError as e:
        logger.error(f"NubeFact request error: {e}")
        raise NubefactError(f"Error de conexión con NubeFact: {str(e)}")


async def void_in_nubefact(payload: dict, *, token: str | None = None) -> dict:
    """Envía solicitud de anulación a NubeFact API."""
    return await emit_to_nubefact(payload, token=token)


def parse_nubefact_response(response_data: dict) -> tuple[SunatStatus, str | None]:
    """
    Interpreta la respuesta de NubeFact y retorna el estado SUNAT
    y un posible mensaje de error.
    """
    accepted = response_data.get("aceptada_por_sunat", False)
    description = response_data.get("sunat_description", "")

    if accepted:
        return SunatStatus.ACCEPTED, None
    else:
        return SunatStatus.REJECTED, description or "Rechazado por SUNAT"
