"""
Modelo Patient — Pacientes de cada clínica.
DNI como identificador único per NTS 139.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True,
        comment="Organización a la que pertenece (null = clínica independiente)"
    )

    # ── Datos de identidad (PII cifrado en campos sensibles) ──
    dni: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="DNI cifrado con Fernet — índice sobre hash"
    )
    dni_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True,
        comment="SHA-256 de clinic_id+dni para búsquedas sin descifrar"
    )
    org_dni_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, unique=True,
        comment="SHA-256 de org_id+dni para dedup cross-sede (null si clínica independiente)"
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Datos personales ─────────────────────────────
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(
        String(20), comment="masculino, femenino, otro"
    )
    phone: Mapped[str | None] = mapped_column(
        String(255), comment="Cifrado con Fernet"
    )
    email: Mapped[str | None] = mapped_column(
        String(255), comment="Cifrado con Fernet"
    )
    address: Mapped[str | None] = mapped_column(String(500))

    # ── Datos médicos ────────────────────────────────
    blood_type: Mapped[str | None] = mapped_column(
        String(5), comment="A+, A-, B+, B-, O+, O-, AB+, AB-"
    )
    allergies: Mapped[dict | None] = mapped_column(
        JSONB, default=list,
        comment='Lista de alergias: [{"name": "...", "severity": "..."}]'
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(String(200))
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(255), comment="Cifrado con Fernet"
    )
    notes: Mapped[str | None] = mapped_column(
        String(1000), comment="Notas adicionales del paciente"
    )

    # ── Datos obstétricos ─────────────────────────────
    fur: Mapped[date | None] = mapped_column(
        Date, comment="Fecha de Última Regla (FUR) para cálculo de semanas gestacionales"
    )

    # ── Estado ───────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relaciones ───────────────────────────────────
    clinic: Mapped["Clinic"] = relationship(  # noqa: F821
        "Clinic", back_populates="patients"
    )
    organization: Mapped["Organization | None"] = relationship(  # noqa: F821
        "Organization"
    )
    clinic_links: Mapped[list["PatientClinicLink"]] = relationship(  # noqa: F821
        "PatientClinicLink", back_populates="patient", lazy="selectin"
    )
    medical_records: Mapped[list["MedicalRecord"]] = relationship("MedicalRecord", back_populates="patient")
    lab_orders: Mapped[list["LabOrder"]] = relationship("LabOrder", back_populates="patient")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def gestational_weeks(self) -> float | None:
        """Calcula semanas gestacionales desde la FUR."""
        if self.fur is None:
            return None
        delta = date.today() - self.fur
        weeks = round(delta.days / 7, 1)
        return weeks if weeks >= 0 else None

    def __repr__(self) -> str:
        return f"<Patient {self.first_name} {self.last_name}>"
