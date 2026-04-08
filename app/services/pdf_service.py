"""
Servicio de renderizado de PDF para informes de imagenología.

Usa Jinja2 para componer HTML desde plantillas en `app/templates/imaging/`
y WeasyPrint para producir bytes PDF listos para descarga.
"""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.security import decrypt_pii
from app.models.clinic import Clinic
from app.models.imaging_report import ImagingReport, ImagingStudyType
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


def render_prescription_pdf(
    *,
    prescription: Prescription,
    patient: Patient,
    doctor: User | None,
    clinic: Clinic,
) -> bytes:
    """Renderiza una receta médica a PDF (bytes)."""
    from weasyprint import CSS, HTML

    template = _rx_env.get_template("prescription.html")

    doctor_name = (
        f"{doctor.first_name} {doctor.last_name}" if doctor else None
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

    items = [
        {
            "medication": it.medication,
            "presentation": it.presentation,
            "dose": it.dose,
            "frequency": it.frequency,
            "duration": it.duration,
            "quantity": it.quantity,
            "instructions": it.instructions,
        }
        for it in prescription.items
    ]

    html_str = template.render(
        clinic=clinic,
        patient_name=patient_name,
        patient_age=_calculate_age(patient.birth_date),
        patient_document=_safe_decrypt(patient.dni),
        doctor_name=doctor_name,
        report_date=_format_date_es(prescription.created_at),
        diagnosis=prescription.diagnosis,
        cie10_code=prescription.cie10_code,
        notes=prescription.notes,
        serial_number=prescription.serial_number,
        items=items,
        is_signed=prescription.signed_at is not None,
        signed_date=signed_date,
        signer_name=signer_name,
    )

    css_path = _RX_TEMPLATES_DIR / "styles.css"
    stylesheets = [CSS(filename=str(css_path))] if css_path.exists() else []

    return HTML(string=html_str, base_url=str(_RX_TEMPLATES_DIR)).write_pdf(
        stylesheets=stylesheets
    )
