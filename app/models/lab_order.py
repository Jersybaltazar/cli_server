import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class LabOrderStatus(str, enum.Enum):
    """Estados del flujo de una orden de laboratorio."""
    ORDERED = "ordered"           # Orden creada
    SAMPLE_TAKEN = "sample_taken" # Muestra tomada
    SENT = "sent"                 # Enviada a laboratorio
    RESULT_RECEIVED = "result_received"  # Resultado recibido
    DELIVERED = "delivered"       # Entregado a paciente
    CANCELLED = "cancelled"

class LabStudyType(str, enum.Enum):
    """Tipos de estudios de laboratorio y patología."""
    ROUTINE = "routine"           # Hemograma, glucosa, etc.
    CYTOLOGY = "cytology"         # PAP (CITO 26)
    PATHOLOGY = "pathology"       # Biopsia (PATO 26)
    HPV_TEST = "hpv_test"         # Test VPH (TEST-PVH)
    FETAL_DNA = "fetal_dna"       # ADN Fetal (ADN FETAL)
    IMAGING = "imaging"           # Ecografías
    OTHER = "other"

class LabOrder(Base):
    """
    Representa una orden de laboratorio o patología.
    Sigue el ciclo de vida desde la orden médica hasta la entrega de resultados.
    """
    __tablename__ = "lab_orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    appointment_id: Mapped[UUID | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)

    # Tipo y descripción
    study_type: Mapped[LabStudyType] = mapped_column(Enum(LabStudyType), index=True)
    study_name: Mapped[str] = mapped_column(String(200)) # "PAP Convencional", etc.

    # Estado y tracking
    status: Mapped[LabOrderStatus] = mapped_column(
        Enum(LabOrderStatus), 
        default=LabOrderStatus.ORDERED,
        index=True
    )

    # Fechas de tracking (workflow)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sample_taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_taken_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_lab_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    external_lab_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    result_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Notas
    clinical_indication: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )

    # Relaciones
    clinic: Mapped["Clinic"] = relationship("Clinic")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="lab_orders")
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])
    sample_taker: Mapped["User | None"] = relationship("User", foreign_keys=[sample_taken_by])
    appointment: Mapped["Appointment | None"] = relationship("Appointment")
    result: Mapped["LabResult | None"] = relationship("LabResult", back_populates="lab_order", uselist=False)

# Actualizar Patient para incluir la relación si es necesario
# (Se hará en un paso posterior si Patient no tiene backref ya definido)
