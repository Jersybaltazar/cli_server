"""
Schemas para Invoice — Facturación electrónica SUNAT.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.invoice import FormaPago, SunatStatus, TipoComprobante


# ── Items ────────────────────────────────────────────

class InvoiceItemCreate(BaseModel):
    description: str = Field(..., min_length=2, max_length=500)
    quantity: int = Field(1, ge=1)
    unit_price: Decimal = Field(..., ge=0, decimal_places=2)
    unit_code: str = Field("ZZ", max_length=5, description="ZZ=servicio, NIU=unidad")


class InvoiceItemResponse(BaseModel):
    id: UUID
    description: str
    quantity: int
    unit_code: str
    unit_price: Decimal
    igv_amount: Decimal
    total: Decimal
    # Campos adicionales para el frontend
    service_type: str = ""
    subtotal: Decimal = Decimal("0.00")

    model_config = {"from_attributes": True}


# ── Invoice ──────────────────────────────────────────

class InvoiceCreate(BaseModel):
    patient_id: UUID | None = None
    appointment_id: UUID | None = None
    tipo_comprobante: TipoComprobante
    cliente_tipo_doc: str = Field("1", max_length=1, description="1=DNI, 6=RUC, 0=Sin doc")
    cliente_numero_doc: str = Field(..., min_length=1, max_length=15)
    cliente_denominacion: str = Field(..., min_length=2, max_length=200)
    cliente_direccion: str | None = Field(None, max_length=500)
    moneda: str = Field("PEN", max_length=3)
    forma_pago: FormaPago = FormaPago.CONTADO
    items: list[InvoiceItemCreate] = Field(..., min_length=1)
    notes: str | None = Field(None, max_length=2000)
    emit_now: bool = Field(True, description="Si true, emite a SUNAT inmediatamente")

    # Campos para Notas de Crédito / Débito
    referenced_invoice_id: UUID | None = Field(
        None, description="ID del comprobante referenciado (requerido para NC/ND)"
    )
    motivo_nota: str | None = Field(
        None, max_length=500, description="Motivo de la nota de crédito/débito"
    )

    @field_validator("cliente_tipo_doc")
    @classmethod
    def validate_tipo_doc(cls, v: str) -> str:
        if v not in ("0", "1", "4", "6", "7", "A"):
            raise ValueError("Tipo de documento inválido. Válidos: 0, 1, 4, 6, 7, A")
        return v

    @model_validator(mode="after")
    def validate_tipo_vs_doc(self):
        if self.tipo_comprobante == TipoComprobante.FACTURA and self.cliente_tipo_doc != "6":
            raise ValueError("Facturas requieren RUC (tipo_doc=6)")
        return self

    @field_validator("referenced_invoice_id")
    @classmethod
    def validate_reference_for_notes(cls, v: UUID | None, info) -> UUID | None:
        tipo = info.data.get("tipo_comprobante")
        if tipo in (TipoComprobante.NOTA_CREDITO, TipoComprobante.NOTA_DEBITO):
            if v is None:
                raise ValueError(
                    "Las notas de crédito/débito requieren un comprobante de referencia"
                )
        return v

    @field_validator("motivo_nota")
    @classmethod
    def validate_motivo_for_notes(cls, v: str | None, info) -> str | None:
        tipo = info.data.get("tipo_comprobante")
        if tipo in (TipoComprobante.NOTA_CREDITO, TipoComprobante.NOTA_DEBITO):
            if not v or len(v.strip()) < 5:
                raise ValueError(
                    "El motivo de la nota debe tener al menos 5 caracteres"
                )
        return v


class InvoiceItemSimple(BaseModel):
    """Item simplificado desde el frontend."""
    service_type: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(1, ge=1)
    unit_price: Decimal = Field(..., ge=0)


class InvoiceCreateSimple(BaseModel):
    """
    Schema simplificado para el frontend.
    El backend resuelve datos del paciente y mapea invoice_type → tipo_comprobante.
    """
    patient_id: UUID | None = Field(
        None, description="ID del paciente (requerido para boletas, opcional para facturas)"
    )
    invoice_type: str = Field(
        ..., description="factura | boleta | nota_credito | nota_debito"
    )
    ruc_client: str | None = Field(None, max_length=15)
    razon_social: str | None = Field(None, max_length=200)
    direccion_cliente: str | None = Field(None, max_length=500)
    items: list[InvoiceItemSimple] = Field(..., min_length=1)
    notes: str | None = Field(None, max_length=2000)

    # Campos para NC/ND
    referenced_invoice_id: UUID | None = None
    motivo_nota: str | None = Field(None, max_length=500)

    @field_validator("invoice_type")
    @classmethod
    def validate_invoice_type(cls, v: str) -> str:
        valid = ("factura", "boleta", "nota_credito", "nota_debito")
        if v not in valid:
            raise ValueError(f"Tipo inválido. Válidos: {', '.join(valid)}")
        return v

    @model_validator(mode="after")
    def validate_patient_or_ruc(self):
        """Boletas requieren paciente; facturas requieren RUC."""
        if self.invoice_type == "factura":
            if not self.ruc_client or len(self.ruc_client) != 11:
                raise ValueError("Las facturas requieren un RUC de 11 dígitos")
            if not self.razon_social or len(self.razon_social.strip()) < 2:
                raise ValueError("Las facturas requieren razón social")
        else:
            if self.patient_id is None:
                raise ValueError("Las boletas y notas requieren patient_id")
        return self


class InvoiceRefEmbed(BaseModel):
    """Datos mínimos del comprobante referenciado (para NC/ND)."""
    id: UUID
    serie: str
    correlativo: int
    numero_comprobante: str
    tipo_comprobante: TipoComprobante
    total: Decimal

    model_config = {"from_attributes": True}


_TIPO_TO_FRONTEND = {
    TipoComprobante.FACTURA: "factura",
    TipoComprobante.BOLETA: "boleta",
    TipoComprobante.NOTA_CREDITO: "nota_credito",
    TipoComprobante.NOTA_DEBITO: "nota_debito",
}


class PatientEmbed(BaseModel):
    """Datos mínimos del paciente embebido en la factura."""
    id: UUID
    first_name: str
    last_name: str
    document_number: str | None = None


class InvoiceResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID | None = None
    appointment_id: UUID | None = None
    created_by: UUID
    tipo_comprobante: TipoComprobante
    serie: str
    correlativo: int
    numero_comprobante: str
    cliente_tipo_doc: str
    cliente_numero_doc: str
    cliente_denominacion: str
    cliente_direccion: str | None = None
    moneda: str
    subtotal: Decimal
    igv: Decimal
    total: Decimal
    forma_pago: FormaPago
    sunat_status: SunatStatus
    sunat_error_message: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None
    cdr_url: str | None = None
    notes: str | None = None
    voided_reason: str | None = None
    voided_at: datetime | None = None
    items: list[InvoiceItemResponse] = []
    issued_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Referencia para NC/ND
    referenced_invoice_id: UUID | None = None
    motivo_nota: str | None = None
    referenced_invoice: InvoiceRefEmbed | None = None

    # Paciente embebido
    patient: PatientEmbed | None = None

    # Campos amigables para el frontend
    invoice_type: str | None = None
    status: str | None = None
    ruc_client: str | None = None
    razon_social: str | None = None
    patient_name: str | None = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    """Respuesta paginada de listado de comprobantes."""
    items: list[InvoiceResponse]
    total: int
    page: int
    size: int
    pages: int


class InvoiceVoidRequest(BaseModel):
    """Request para anular un comprobante."""
    reason: str = Field(..., min_length=5, max_length=500, description="Motivo de anulación")


class InvoiceRetryResponse(BaseModel):
    invoice_id: UUID
    sunat_status: SunatStatus
    message: str
