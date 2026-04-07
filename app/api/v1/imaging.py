"""
Endpoints REST para informes de imagenología.

Permisos:
- Crear/editar/eliminar: doctor, obstetra o admin+
- Leer: mismos roles (clinic-scoped)
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.imaging_report import ImagingStudyType
from app.models.user import User, UserRole
from app.schemas.imaging_report import (
    ImagingReportCreate,
    ImagingReportListResponse,
    ImagingReportResponse,
    ImagingReportUpdate,
)
from app.services import imaging_service
from app.services.pdf_service import render_imaging_pdf

router = APIRouter()


_CLINICAL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)

_EDITOR_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post(
    "",
    response_model=ImagingReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_imaging_report(
    data: ImagingReportCreate,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nuevo informe de imagenología."""
    return await imaging_service.create_report(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.get("", response_model=ImagingReportListResponse)
async def list_imaging_reports(
    patient_id: UUID | None = Query(None),
    study_type: ImagingStudyType | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Lista informes con filtros opcionales (ordenados por fecha desc)."""
    return await imaging_service.list_reports(
        db,
        clinic_id=user.clinic_id,
        patient_id=patient_id,
        study_type=study_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{report_id}", response_model=ImagingReportResponse)
async def get_imaging_report(
    report_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Detalle de un informe de imagenología."""
    return await imaging_service.get_report(
        db, clinic_id=user.clinic_id, report_id=report_id
    )


@router.patch("/{report_id}", response_model=ImagingReportResponse)
async def update_imaging_report(
    report_id: UUID,
    data: ImagingReportUpdate,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Edita un informe. Falla con 403 si el MedicalRecord asociado está firmado."""
    return await imaging_service.update_report(
        db,
        user=user,
        report_id=report_id,
        data=data,
        ip_address=_get_client_ip(request),
    )


@router.post("/{report_id}/sign", response_model=ImagingReportResponse)
async def sign_imaging_report(
    report_id: UUID,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Firma digitalmente un informe. Una vez firmado es inmutable."""
    return await imaging_service.sign_report(
        db,
        user=user,
        report_id=report_id,
        ip_address=_get_client_ip(request),
    )


@router.get(
    "/{report_id}/pdf",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_imaging_pdf(
    report_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Descarga el informe en formato PDF con membrete de la clínica."""
    report = await imaging_service.get_report_raw(
        db, clinic_id=user.clinic_id, report_id=report_id
    )
    pdf_bytes = render_imaging_pdf(
        report=report,
        patient=report.patient,
        doctor=report.doctor,
        clinic=report.clinic,
    )
    filename = f"informe-{report.study_type.value}-{report.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_imaging_report(
    report_id: UUID,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Elimina un informe. Falla con 403 si el MedicalRecord asociado está firmado."""
    await imaging_service.delete_report(
        db,
        user=user,
        report_id=report_id,
        ip_address=_get_client_ip(request),
    )
    return None
