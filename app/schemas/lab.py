from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.lab_order import LabOrderStatus, LabStudyType

# ── Lab Order Schemas ──────────────────────────────────────────

class LabOrderBase(BaseModel):
    study_type: LabStudyType
    study_name: str = Field(..., max_length=200)
    clinical_indication: str
    notes: str | None = None

class LabOrderCreate(LabOrderBase):
    patient_id: UUID
    doctor_id: UUID | None = None  # Si es None, se usa el current_user
    appointment_id: UUID | None = None

class LabOrderUpdate(BaseModel):
    status: LabOrderStatus | None = None
    sample_taken_at: datetime | None = None
    sample_taken_by: UUID | None = None
    sent_at: datetime | None = None
    external_lab_name: str | None = Field(None, max_length=200)
    external_lab_code: str | None = Field(None, max_length=50)
    result_received_at: datetime | None = None
    delivered_at: datetime | None = None
    notes: str | None = None

class LabOrderResponse(LabOrderBase):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    doctor_id: UUID
    appointment_id: UUID | None
    
    status: LabOrderStatus
    ordered_at: datetime
    sample_taken_at: datetime | None
    sample_taken_by: UUID | None
    sent_at: datetime | None
    external_lab_name: str | None
    external_lab_code: str | None
    result_received_at: datetime | None
    delivered_at: datetime | None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ── Lab Result Schemas ─────────────────────────────────────────

class LabResultBase(BaseModel):
    result_summary: str
    result_detail: dict = Field(default_factory=dict)
    attachments: list[dict] = Field(default_factory=list)

class LabResultCreate(LabResultBase):
    lab_order_id: UUID
    # medical_record_id se puede setear internamente si se crea automáticamente

class LabResultResponse(LabResultBase):
    id: UUID
    lab_order_id: UUID
    clinic_id: UUID
    recorded_by: UUID
    recorded_at: datetime
    medical_record_id: UUID | None

    class Config:
        from_attributes = True

# ── Dashboard & Stats ───────────────────────────────────────────

class LabDashboardStats(BaseModel):
    total_orders: int
    pending_samples: int
    sent_awaiting: int
    results_to_deliver: int
    overdue: int

class LabOrderListResponse(BaseModel):
    items: list[LabOrderResponse]
    total: int
    pending_count: int
    overdue_count: int
