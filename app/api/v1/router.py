"""
Router principal de la API v1.
Agrupa todos los sub-routers de la versión 1.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.clinic import router as clinic_router
from app.api.v1.users import router as users_router
from app.api.v1.patients import router as patients_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.public_booking import router as public_booking_router
from app.api.v1.records import router as records_router
from app.api.v1.cie10 import router as cie10_router
from app.api.v1.dental_charts import router as dental_charts_router
from app.api.v1.prenatal import router as prenatal_router
from app.api.v1.ophthalmic import router as ophthalmic_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.reports import router as reports_router
from app.api.v1.cash_register import router as cash_register_router
from app.api.v1.logistica import router as logistica_router
from app.api.v1.services import router as services_router
from app.api.v1.sync import router as sync_router
from app.api.v1.reniec import router as reniec_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.sms import router as sms_router
from app.api.v1.staff_schedules import router as staff_schedules_router
from app.api.v1.lab import router as lab_router

api_v1_router = APIRouter()

api_v1_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Autenticación"],
)

api_v1_router.include_router(
    clinic_router,
    prefix="/clinic",
    tags=["Clínica"],
)

api_v1_router.include_router(
    users_router,
    prefix="/users",
    tags=["Usuarios"],
)

api_v1_router.include_router(
    patients_router,
    prefix="/patients",
    tags=["Pacientes"],
)

api_v1_router.include_router(
    appointments_router,
    prefix="/appointments",
    tags=["Citas"],
)

api_v1_router.include_router(
    schedules_router,
    prefix="/schedules",
    tags=["Horarios de Doctores"],
)

api_v1_router.include_router(
    public_booking_router,
    prefix="/public/booking",
    tags=["Reserva Pública"],
)

api_v1_router.include_router(
    records_router,
    prefix="/records",
    tags=["Historia Clínica (HCE)"],
)

api_v1_router.include_router(
    cie10_router,
    prefix="/cie10",
    tags=["CIE-10"],
)

api_v1_router.include_router(
    dental_charts_router,
    prefix="/dental-charts",
    tags=["Odontograma"],
)

api_v1_router.include_router(
    prenatal_router,
    prefix="/prenatal",
    tags=["Control Prenatal"],
)

api_v1_router.include_router(
    ophthalmic_router,
    prefix="/ophthalmic",
    tags=["Oftalmología"],
)

api_v1_router.include_router(
    invoices_router,
    prefix="/invoices",
    tags=["Facturación SUNAT"],
)

api_v1_router.include_router(
    reports_router,
    prefix="/reports",
    tags=["Reportes"],
)

api_v1_router.include_router(
    cash_register_router,
    prefix="/cash-register",
    tags=["Caja"],
)

api_v1_router.include_router(
    logistica_router,
    prefix="/logistica",
    tags=["Logística"],
)

api_v1_router.include_router(
    services_router,
    prefix="/services",
    tags=["Servicios"],
)

api_v1_router.include_router(
    sync_router,
    prefix="/sync",
    tags=["Sincronización Offline"],
)

api_v1_router.include_router(
    reniec_router,
    prefix="/reniec",
    tags=["Consultas DNI / RUC"],
)

api_v1_router.include_router(
    organizations_router,
    prefix="/organizations",
    tags=["Organizaciones"],
)

api_v1_router.include_router(
    sms_router,
    prefix="/sms",
    tags=["SMS / Notificaciones"],
)

api_v1_router.include_router(
    lab_router,
    prefix="/lab",
    tags=["Laboratorio y Patología"],
)

api_v1_router.include_router(
    staff_schedules_router,
    prefix="/staff-schedules",
    tags=["Turnos de Personal"],
)
