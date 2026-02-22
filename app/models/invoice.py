"""
Modelo Invoice + InvoiceItem — Facturación electrónica SUNAT.

Campos alineados con los requerimientos de NubeFact API:
serie, correlativo, tipo_comprobante, moneda, forma_pago, IGV.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoComprobante(str, enum.Enum):
    """Tipos de comprobante SUNAT."""
    FACTURA = "01"
    BOLETA = "03"
    NOTA_CREDITO = "07"
    NOTA_DEBITO = "08"


class SunatStatus(str, enum.Enum):
    """Estados del comprobante frente a SUNAT."""
    PENDING = "pending"          # Pendiente de emisión
    QUEUED = "queued"            # En cola (offline)
    EMITTED = "emitted"          # Enviado a NubeFact
    ACCEPTED = "accepted"        # Aceptado por SUNAT
    REJECTED = "rejected"        # Rechazado por SUNAT
    VOIDED = "voided"            # Anulado
    ERROR = "error"              # Error de comunicación


class FormaPago(str, enum.Enum):
    """Formas de pago SUNAT."""
    CONTADO = "Contado"
    CREDITO = "Credito"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id")
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"),
        comment="Cita asociada (opcional)"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # ── Datos SUNAT del comprobante ──────────────────
    tipo_comprobante: Mapped[TipoComprobante] = mapped_column(
        Enum(TipoComprobante), nullable=False
    )
    serie: Mapped[str] = mapped_column(
        String(4), nullable=False,
        comment="Serie: F001 (factura), B001 (boleta)"
    )
    correlativo: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Número correlativo autogenerado"
    )

    # ── Datos del cliente ────────────────────────────
    cliente_tipo_doc: Mapped[str] = mapped_column(
        String(1), nullable=False, default="1",
        comment="Tipo documento: 1=DNI, 6=RUC, 0=Sin doc"
    )
    cliente_numero_doc: Mapped[str] = mapped_column(
        String(15), nullable=False,
        comment="Número de documento del cliente"
    )
    cliente_denominacion: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nombre o razón social del cliente"
    )
    cliente_direccion: Mapped[str | None] = mapped_column(String(500))

    # ── Montos ───────────────────────────────────────
    moneda: Mapped[str] = mapped_column(
        String(3), nullable=False, default="PEN",
        comment="Moneda: PEN (soles), USD (dólares)"
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Subtotal sin IGV"
    )
    igv: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="IGV (18%)"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Total con IGV"
    )
    forma_pago: Mapped[FormaPago] = mapped_column(
        Enum(FormaPago), nullable=False, default=FormaPago.CONTADO
    )

    # ── Estado SUNAT ─────────────────────────────────
    sunat_status: Mapped[SunatStatus] = mapped_column(
        Enum(SunatStatus), nullable=False, default=SunatStatus.PENDING
    )
    nubefact_response: Mapped[dict | None] = mapped_column(
        JSONB, default=dict,
        comment="Respuesta completa de NubeFact API"
    )
    sunat_error_message: Mapped[str | None] = mapped_column(
        Text, comment="Mensaje de error de SUNAT si fue rechazado"
    )
    pdf_url: Mapped[str | None] = mapped_column(
        String(500), comment="URL del PDF generado por NubeFact"
    )
    xml_url: Mapped[str | None] = mapped_column(
        String(500), comment="URL del XML firmado"
    )
    cdr_url: Mapped[str | None] = mapped_column(
        String(500), comment="URL del CDR (constancia de recepción)"
    )

    # ── Referencia para Notas de Crédito / Débito ───
    referenced_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"),
        comment="Comprobante original referenciado (para NC/ND)"
    )
    motivo_nota: Mapped[str | None] = mapped_column(
        String(500),
        comment="Motivo de la nota de crédito/débito"
    )

    # ── Notas / observaciones ────────────────────────
    notes: Mapped[str | None] = mapped_column(Text)
    voided_reason: Mapped[str | None] = mapped_column(
        String(500), comment="Motivo de anulación"
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Timestamps ───────────────────────────────────
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Fecha de emisión"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship("Clinic")  # noqa: F821
    patient: Mapped["Patient"] = relationship("Patient")  # noqa: F821
    items: Mapped[list["InvoiceItem"]] = relationship(
        "InvoiceItem", back_populates="invoice", lazy="selectin"
    )
    referenced_invoice: Mapped["Invoice | None"] = relationship(
        "Invoice", remote_side="Invoice.id", foreign_keys=[referenced_invoice_id]
    )

    # ── Índices ──────────────────────────────────────
    __table_args__ = (
        Index("idx_invoice_clinic_status", "clinic_id", "sunat_status"),
        Index("idx_invoice_serie_corr", "clinic_id", "serie", "correlativo", unique=True),
        Index("idx_invoice_patient", "clinic_id", "patient_id"),
        Index("idx_invoice_issued", "clinic_id", "issued_at"),
    )

    @property
    def numero_comprobante(self) -> str:
        return f"{self.serie}-{self.correlativo:08d}"

    def __repr__(self) -> str:
        return f"<Invoice {self.numero_comprobante} [{self.sunat_status.value}] S/{self.total}>"


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # ── Datos del ítem ───────────────────────────────
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    unit_code: Mapped[str] = mapped_column(
        String(5), nullable=False, default="ZZ",
        comment="Código SUNAT de unidad de medida: ZZ=servicio, NIU=unidad"
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Precio unitario sin IGV"
    )
    igv_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="IGV del ítem"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Total del ítem con IGV"
    )

    # ── Relaciones ───────────────────────────────────
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")

    def __repr__(self) -> str:
        return f"<InvoiceItem {self.description} x{self.quantity} S/{self.total}>"
