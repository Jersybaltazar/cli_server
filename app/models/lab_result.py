from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class LabResult(Base):
    """
    Resultados detallados de una orden de laboratorio.
    Almacena datos estructurados por tipo de estudio.
    """
    __tablename__ = "lab_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    lab_order_id: Mapped[UUID] = mapped_column(ForeignKey("lab_orders.id"), unique=True, index=True)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    # Resultado general
    result_summary: Mapped[str] = mapped_column(Text)
    
    # Datos estructurados según el tipo de estudio (PAP, VPH, ADN, etc.)
    # Ejemplo PAP: {"classification": "ASCUS", "bethesda": "...", "adequacy": "satisfactory"}
    # Ejemplo VPH: {"result": "positive", "genotypes": [16, 18]}
    result_detail: Mapped[dict] = mapped_column(JSONB, server_default='{}')

    # Archivos adjuntos (PDFs del laboratorio, etc.)
    # Formato: [{"name": "resultado.pdf", "url": "..."}]
    attachments: Mapped[list] = mapped_column(JSONB, server_default='[]')

    # Auditoría de quién registró el resultado
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relación con HCE (opcional, si se genera un registro automático)
    medical_record_id: Mapped[UUID | None] = mapped_column(ForeignKey("medical_records.id"), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )

    # Relaciones
    lab_order: Mapped["LabOrder"] = relationship("LabOrder", back_populates="result")
    clinic: Mapped["Clinic"] = relationship("Clinic")
    recorder: Mapped["User"] = relationship("User")
    medical_record: Mapped["MedicalRecord | None"] = relationship("MedicalRecord")
