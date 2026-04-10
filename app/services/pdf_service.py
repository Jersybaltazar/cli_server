"""
Servicio de renderizado de PDF para informes de imagenología.

Usa Jinja2 para componer HTML desde plantillas en `app/templates/imaging/`
y WeasyPrint para producir bytes PDF listos para descarga.
"""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.core.security import decrypt_pii
from app.models.clinic import Clinic
from app.models.imaging_report import ImagingReport, ImagingStudyType
from app.models.lab_order import LabOrder, LabStudyType
from app.models.lab_result import LabResult
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.user import User

# ── Helpers ──────────────────────────────────────────

def _safe_decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return decrypt_pii(value)
    except Exception:
        return None


# ── Configuración Jinja2 ─────────────────────────────

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "imaging"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

_RX_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "prescriptions"

_rx_env = Environment(
    loader=FileSystemLoader(str(_RX_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

_LAB_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "lab"

_lab_env = Environment(
    loader=FileSystemLoader(str(_LAB_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

# ── Mapeo tipo → plantilla ───────────────────────────
# En Fase 1 todos los tipos usan generic.html. En fases posteriores cada
# tipo tendrá su plantilla específica (pelvic.html, transvaginal.html, etc.).

_TEMPLATE_MAP: dict[ImagingStudyType, str] = {
    t: "generic.html" for t in ImagingStudyType
}
# Fase 2 — plantillas específicas para los 5 tipos simples
_TEMPLATE_MAP[ImagingStudyType.PELVIC] = "pelvic.html"
_TEMPLATE_MAP[ImagingStudyType.TRANSVAGINAL] = "transvaginal.html"
_TEMPLATE_MAP[ImagingStudyType.OBSTETRIC_FIRST] = "obstetric_first.html"
_TEMPLATE_MAP[ImagingStudyType.BREAST] = "breast.html"
_TEMPLATE_MAP[ImagingStudyType.HYSTEROSONOGRAPHY] = "hysterosonography.html"
# Fase 3 — plantillas obstétricas medianas
_TEMPLATE_MAP[ImagingStudyType.OBSTETRIC_SECOND_THIRD] = "obstetric_second_third.html"
_TEMPLATE_MAP[ImagingStudyType.OBSTETRIC_DOPPLER] = "obstetric_doppler.html"
_TEMPLATE_MAP[ImagingStudyType.OBSTETRIC_TWIN] = "obstetric_twin.html"
_TEMPLATE_MAP[ImagingStudyType.OBSTETRIC_TWIN_DOPPLER] = "obstetric_twin_doppler.html"
# Fase 4 — plantillas complejas
_TEMPLATE_MAP[ImagingStudyType.MORPHOLOGIC] = "morphologic.html"
_TEMPLATE_MAP[ImagingStudyType.GENETIC] = "genetic.html"
_TEMPLATE_MAP[ImagingStudyType.COLPOSCOPY] = "colposcopy.html"


_STUDY_LABELS: dict[ImagingStudyType, str] = {
    ImagingStudyType.PELVIC: "Ecografía Pélvica",
    ImagingStudyType.TRANSVAGINAL: "Ecografía Transvaginal",
    ImagingStudyType.OBSTETRIC_FIRST: "Ecografía Obstétrica — 1er Trimestre",
    ImagingStudyType.OBSTETRIC_SECOND_THIRD: "Ecografía Obstétrica — 2do/3er Trimestre",
    ImagingStudyType.OBSTETRIC_DOPPLER: "Ecografía Obstétrica Doppler",
    ImagingStudyType.OBSTETRIC_TWIN: "Ecografía Obstétrica Gemelar",
    ImagingStudyType.OBSTETRIC_TWIN_DOPPLER: "Ecografía Obstétrica Gemelar Doppler",
    ImagingStudyType.BREAST: "Ecografía Mamaria",
    ImagingStudyType.MORPHOLOGIC: "Ecografía Morfológica",
    ImagingStudyType.GENETIC: "Ecografía Genética / Morfogenética",
    ImagingStudyType.HYSTEROSONOGRAPHY: "Histerosonografía",
    ImagingStudyType.COLPOSCOPY: "Colposcopía",
}


_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre",
]


def _format_date_es(dt: datetime) -> str:
    return f"{dt.day:02d} de {_MONTHS_ES[dt.month - 1]} de {dt.year}"


def _calculate_age(birth_date) -> int | None:
    if birth_date is None:
        return None
    today = datetime.utcnow().date()
    return (
        today.year - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def render_imaging_pdf(
    *,
    report: ImagingReport,
    patient: Patient,
    doctor: User | None,
    clinic: Clinic,
) -> bytes:
    """Renderiza un informe de imagenología a PDF (bytes)."""
    # Import perezoso: WeasyPrint carga librerías nativas pesadas.
    from weasyprint import CSS, HTML

    template_name = _TEMPLATE_MAP.get(report.study_type, "generic.html")
    template = _env.get_template(template_name)

    doctor_name = (
        f"{doctor.first_name} {doctor.last_name}" if doctor else None
    )
    patient_name = f"{patient.first_name} {patient.last_name}"

    signer_name = None
    signed_date = None
    if report.signed_at is not None:
        signed_date = _format_date_es(report.signed_at)
        if report.signer:
            signer_name = f"{report.signer.first_name} {report.signer.last_name}"

    html_str = template.render(
        clinic=clinic,
        study_label=_STUDY_LABELS.get(report.study_type, "Informe de Imagenología"),
        patient_name=patient_name,
        patient_age=_calculate_age(patient.birth_date),
        patient_document=_safe_decrypt(patient.dni),
        doctor_name=doctor_name,
        report_date=_format_date_es(report.created_at),
        findings=report.findings or {},
        conclusion_items=report.conclusion_items or [],
        recommendations=report.recommendations,
        is_signed=report.signed_at is not None,
        signed_date=signed_date,
        signer_name=signer_name,
    )

    css_path = _TEMPLATES_DIR / "styles.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []

    return HTML(string=html_str, base_url=str(_TEMPLATES_DIR)).write_pdf(
        stylesheets=stylesheets
    )


def _generate_qr_base64(url: str) -> str:
    """Genera un QR code como data URI base64 (PNG)."""
    import base64
    import io
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def render_prescription_pdf(
    *,
    prescription: Prescription,
    patient: Patient,
    doctor: User | None,
    clinic: Clinic,
    controlled_info: dict | None = None,
) -> bytes:
    """Renderiza una receta médica a PDF (bytes).

    Si `prescription.kind == "controlled"` se usa la plantilla
    `prescription_controlled.html` (triplicado A4 horizontal — paciente /
    farmacia / archivo).

    `controlled_info` es un dict opcional con metadatos por-item para la
    receta controlada: `{medication_id: "IIA" | "IIIA" | "IIIB", ...}`.
    """
    from weasyprint import CSS, HTML

    is_controlled = (prescription.kind or "common") == "controlled"
    template_name = (
        "prescription_controlled.html" if is_controlled else "prescription.html"
    )
    template = _rx_env.get_template(template_name)

    doctor_name = (
        f"{doctor.first_name} {doctor.last_name}" if doctor else None
    )
    doctor_cmp = doctor.cmp_number if doctor else None
    doctor_authorization_number = (
        doctor.controlled_authorization_number if doctor else None
    )
    patient_name = f"{patient.first_name} {patient.last_name}"

    signer_name = None
    signed_date = None
    if prescription.signed_at is not None:
        signed_date = _format_date_es(prescription.signed_at)
        if prescription.signer:
            signer_name = (
                f"{prescription.signer.first_name} {prescription.signer.last_name}"
            )

    valid_until_label = None
    if prescription.valid_until:
        d = prescription.valid_until
        valid_until_label = f"{d.day:02d} de {_MONTHS_ES[d.month - 1]} de {d.year}"

    controlled_info = controlled_info or {}
    items = [
        {
            "medication": it.medication,
            "presentation": it.presentation,
            "dose": it.dose,
            "frequency": it.frequency,
            "duration": it.duration,
            "quantity": it.quantity,
            "instructions": it.instructions,
            "controlled_list": controlled_info.get(str(it.medication_id)),
        }
        for it in prescription.items
    ]

    # Fase 2.5 — QR de verificación
    qr_data_uri = None
    if prescription.verification_token and prescription.signed_at:
        _settings = get_settings()
        # En prod usar dominio real; en dev usar localhost:3000
        base_url = (
            "https://app.clinicsaas.pe"
            if _settings.is_production
            else "http://localhost:3000"
        )
        verify_url = (
            f"{base_url}/verificar/{prescription.id}"
            f"?token={prescription.verification_token}"
        )
        qr_data_uri = _generate_qr_base64(verify_url)

    html_str = template.render(
        clinic=clinic,
        patient_name=patient_name,
        patient_age=_calculate_age(patient.birth_date),
        patient_document=_safe_decrypt(patient.dni),
        patient_address=patient.address,
        doctor_name=doctor_name,
        doctor_cmp=doctor_cmp,
        doctor_authorization_number=doctor_authorization_number,
        report_date=_format_date_es(prescription.created_at),
        diagnosis=prescription.diagnosis,
        cie10_code=prescription.cie10_code,
        notes=prescription.notes,
        serial_number=prescription.serial_number,
        kind=prescription.kind or "common",
        is_controlled=is_controlled,
        valid_until=valid_until_label,
        items=items,
        is_signed=prescription.signed_at is not None,
        signed_date=signed_date,
        signer_name=signer_name,
        qr_data_uri=qr_data_uri,
    )

    css_path = _RX_TEMPLATES_DIR / "styles.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []

    return HTML(string=html_str, base_url=str(_RX_TEMPLATES_DIR)).write_pdf(
        stylesheets=stylesheets
    )


# ── Laboratorio ─────────────────────────────────────────

_LAB_STUDY_LABELS: dict[LabStudyType, str] = {
    LabStudyType.ROUTINE: "Examen de Rutina",
    LabStudyType.CYTOLOGY: "Citología (PAP)",
    LabStudyType.PATHOLOGY: "Anatomía Patológica",
    LabStudyType.HPV_TEST: "Test VPH",
    LabStudyType.FETAL_DNA: "ADN Fetal",
    LabStudyType.IMAGING: "Imagenología",
    LabStudyType.OTHER: "Otro",
}


def render_lab_order_pdf(
    *,
    order: LabOrder,
    patient: Patient,
    doctor: User | None,
    clinic: Clinic,
) -> bytes:
    """Renderiza una orden de laboratorio a PDF (bytes)."""
    from weasyprint import CSS, HTML

    template = _lab_env.get_template("order.html")

    doctor_name = (
        f"{doctor.first_name} {doctor.last_name}" if doctor else None
    )
    patient_name = f"{patient.first_name} {patient.last_name}"

    html_str = template.render(
        clinic=clinic,
        patient_name=patient_name,
        patient_age=_calculate_age(patient.birth_date),
        patient_document=_safe_decrypt(patient.dni),
        doctor_name=doctor_name,
        order_date=_format_date_es(order.ordered_at),
        study_type_label=_LAB_STUDY_LABELS.get(order.study_type, "Laboratorio"),
        study_name=order.study_name,
        lab_code=order.lab_code,
        cassette_count=order.cassette_count,
        external_lab_name=order.external_lab_name,
        external_lab_code=order.external_lab_code,
        clinical_indication=order.clinical_indication,
        notes=order.notes,
    )

    css_path = _LAB_TEMPLATES_DIR / "styles.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []

    return HTML(string=html_str, base_url=str(_LAB_TEMPLATES_DIR)).write_pdf(
        stylesheets=stylesheets
    )


def render_lab_result_pdf(
    *,
    order: LabOrder,
    result: LabResult,
    patient: Patient,
    doctor: User | None,
    clinic: Clinic,
) -> bytes:
    """Renderiza un resultado de laboratorio a PDF (bytes)."""
    from weasyprint import CSS, HTML

    template = _lab_env.get_template("result.html")

    doctor_name = (
        f"{doctor.first_name} {doctor.last_name}" if doctor else None
    )
    patient_name = f"{patient.first_name} {patient.last_name}"

    recorded_date = None
    if result.recorded_at:
        recorded_date = _format_date_es(result.recorded_at)

    result_date = None
    if order.result_received_at:
        result_date = _format_date_es(order.result_received_at)
    elif result.recorded_at:
        result_date = recorded_date

    html_str = template.render(
        clinic=clinic,
        patient_name=patient_name,
        patient_age=_calculate_age(patient.birth_date),
        patient_document=_safe_decrypt(patient.dni),
        doctor_name=doctor_name,
        order_date=_format_date_es(order.ordered_at),
        result_date=result_date or "—",
        study_type=order.study_type.value if order.study_type else "other",
        study_type_label=_LAB_STUDY_LABELS.get(order.study_type, "Laboratorio"),
        study_name=order.study_name,
        lab_code=order.lab_code,
        external_lab_name=order.external_lab_name,
        external_lab_code=order.external_lab_code,
        clinical_indication=order.clinical_indication,
        result_summary=result.result_summary,
        result_detail=result.result_detail or {},
        recorded_date=recorded_date,
    )

    css_path = _LAB_TEMPLATES_DIR / "styles.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []

    return HTML(string=html_str, base_url=str(_LAB_TEMPLATES_DIR)).write_pdf(
        stylesheets=stylesheets
    )
