"""
Endpoints REST de recetas médicas (prescriptions).
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionListResponse,
    PrescriptionResponse,
    PrescriptionTemplateCreate,
    PrescriptionTemplateListResponse,
    PrescriptionTemplateResponse,
    PrescriptionUpdate,
)
from app.services import prescription_service
from app.services.pdf_service import render_prescription_pdf

router = APIRouter()


_CLINICAL_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.ORG_ADMIN,
    UserRole.CLINIC_ADMIN,
    UserRole.DOCTOR,
    UserRole.OBSTETRA,
)

_EDITOR_ROLES = _CLINICAL_ROLES


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ── Plantillas (deben ir ANTES de /{rx_id}) ──────────

@router.get("/templates", response_model=PrescriptionTemplateListResponse)
async def list_prescription_templates(
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.list_templates(db, clinic_id=user.clinic_id)


@router.post(
    "/templates",
    response_model=PrescriptionTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription_template(
    data: PrescriptionTemplateCreate,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.create_template(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_prescription_template(
    template_id: UUID,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    await prescription_service.delete_template(
        db, user=user, template_id=template_id, ip_address=_get_client_ip(request)
    )
    return None


# ── Recetas ──────────────────────────────────────────

@router.post(
    "",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    data: PrescriptionCreate,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.create_prescription(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.get("", response_model=PrescriptionListResponse)
async def list_prescriptions(
    patient_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.list_prescriptions(
        db,
        clinic_id=user.clinic_id,
        patient_id=patient_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{rx_id}", response_model=PrescriptionResponse)
async def get_prescription(
    rx_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.get_prescription(
        db, clinic_id=user.clinic_id, rx_id=rx_id
    )


@router.patch("/{rx_id}", response_model=PrescriptionResponse)
async def update_prescription(
    rx_id: UUID,
    data: PrescriptionUpdate,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.update_prescription(
        db, user=user, rx_id=rx_id, data=data, ip_address=_get_client_ip(request)
    )


@router.post("/{rx_id}/sign", response_model=PrescriptionResponse)
async def sign_prescription(
    rx_id: UUID,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await prescription_service.sign_prescription(
        db, user=user, rx_id=rx_id, ip_address=_get_client_ip(request)
    )


@router.get(
    "/{rx_id}/pdf",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_prescription_pdf(
    rx_id: UUID,
    user: User = Depends(require_role(*_CLINICAL_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    rx = await prescription_service.get_prescription_raw(
        db, clinic_id=user.clinic_id, rx_id=rx_id
    )
    pdf_bytes = render_prescription_pdf(
        prescription=rx,
        patient=rx.patient,
        doctor=rx.doctor,
        clinic=rx.clinic,
    )
    filename = f"receta-{rx.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.delete("/{rx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription(
    rx_id: UUID,
    request: Request,
    user: User = Depends(require_role(*_EDITOR_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    await prescription_service.delete_prescription(
        db, user=user, rx_id=rx_id, ip_address=_get_client_ip(request)
    )
    return None
