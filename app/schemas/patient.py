"""
Schemas para Patient.
Validación de DNI peruano y campos médicos.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class PatientBase(BaseModel):
    dni: str = Field(
        ..., min_length=8, max_length=15,
        description="DNI o documento de identidad"
    )
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    birth_date: date | None = None
    gender: str | None = Field(
        None, pattern=r"^(masculino|femenino|otro)$"
    )
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(None, max_length=500)
    blood_type: str | None = Field(
        None, pattern=r"^(A|B|AB|O)[+-]$",
        description="Tipo de sangre: A+, A-, B+, B-, O+, O-, AB+, AB-"
    )
    allergies: list[dict] | None = Field(
        None, description='Lista de alergias: [{"name": "...", "severity": "leve|moderada|severa"}]'
    )
    emergency_contact_name: str | None = Field(None, max_length=200)
    emergency_contact_phone: str | None = Field(None, max_length=20)
    notes: str | None = Field(None, max_length=1000)
    fur: date | None = Field(None, description="Fecha de Última Regla (FUR)")

    @field_validator("dni")
    @classmethod
    def validate_dni(cls, v: str) -> str:
        """Valida formato de DNI peruano (8 dígitos) o carné de extranjería."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("DNI no puede estar vacío")
        return cleaned


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=2, max_length=100)
    last_name: str | None = Field(None, min_length=2, max_length=100)
    birth_date: date | None = None
    gender: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(None, max_length=500)
    blood_type: str | None = None
    allergies: list[dict] | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    fur: date | None = None
    is_active: bool | None = None


class PatientClinicInfo(BaseModel):
    """Info de una sede donde el paciente está registrado."""
    clinic_id: UUID
    clinic_name: str | None = None
    registered_at: datetime | None = None


class PatientResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    organization_id: UUID | None = None
    dni: str
    first_name: str
    last_name: str
    full_name: str
    birth_date: date | None = None
    gender: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    blood_type: str | None = None
    allergies: list[dict] | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    fur: date | None = None
    gestational_weeks: float | None = None
    is_active: bool
    registered_sedes: list[PatientClinicInfo] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientListResponse(BaseModel):
    """Respuesta paginada de listado de pacientes."""
    items: list[PatientResponse]
    total: int
    page: int
    size: int
    pages: int
