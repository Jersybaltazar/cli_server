"""Endpoints REST para plantillas de imagenología."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.imaging_report import ImagingStudyType
from app.models.user import User, UserRole
from app.schemas.imaging_template import (
    ImagingTemplateCreate,
    ImagingTemplateListResponse,
    ImagingTemplateResponse,
)
from app.services import imaging_template_service

router = APIRouter()


_ROLES = (
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


@router.get("", response_model=ImagingTemplateListResponse)
async def list_imaging_templates(
    study_type: ImagingStudyType | None = Query(None),
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await imaging_template_service.list_templates(
        db, clinic_id=user.clinic_id, study_type=study_type
    )


@router.post(
    "",
    response_model=ImagingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_imaging_template(
    data: ImagingTemplateCreate,
    request: Request,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await imaging_template_service.create_template(
        db, user=user, data=data, ip_address=_get_client_ip(request)
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_imaging_template(
    template_id: UUID,
    request: Request,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    await imaging_template_service.delete_template(
        db, user=user, template_id=template_id, ip_address=_get_client_ip(request)
    )
    return None
