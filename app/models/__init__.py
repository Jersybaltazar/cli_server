"""
Modelos SQLAlchemy — exportar todos para que Alembic los detecte.
"""

from app.models.organization import Organization
from app.models.clinic import Clinic
from app.models.user import User
from app.models.user_clinic_access import UserClinicAccess
from app.models.patient import Patient
from app.models.patient_clinic_link import PatientClinicLink
from app.models.audit_log import AuditLog
from app.models.appointment import Appointment
from app.models.doctor_schedule import DoctorSchedule
from app.models.medical_record import MedicalRecord
from app.models.dental_chart import DentalChart
from app.models.prenatal_visit import PrenatalVisit
from app.models.ophthalmic_exam import OphthalmicExam
from app.models.invoice import Invoice, InvoiceItem
from app.models.sync_queue import SyncQueue, SyncDeviceMapping
from app.models.lab_order import LabOrder, LabOrderStatus, LabStudyType
from app.models.lab_result import LabResult
from app.models.logistica import Supplier, InventoryCategory, InventoryItem, StockMovement
from app.models.service import Service
from app.models.cie10 import Cie10Code
from app.models.sms_message import SmsMessage
from app.models.staff_schedule_override import StaffScheduleOverride

__all__ = [
    "Organization",
    "Clinic",
    "User",
    "UserClinicAccess",
    "Patient",
    "PatientClinicLink",
    "AuditLog",
    "Appointment",
    "DoctorSchedule",
    "MedicalRecord",
    "DentalChart",
    "PrenatalVisit",
    "OphthalmicExam",
    "Invoice",
    "InvoiceItem",
    "SyncQueue",
    "SyncDeviceMapping",
    "LabOrder",
    "LabOrderStatus",
    "LabStudyType",
    "LabResult",
    "Supplier",
    "InventoryCategory",
    "InventoryItem",
    "StockMovement",
    "Service",
    "Cie10Code",
    "SmsMessage",
    "StaffScheduleOverride",
]
