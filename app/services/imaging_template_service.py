"""Servicio de plantillas de informes de imagenología."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundException
from app.models.imaging_report import ImagingStudyType
from app.models.imaging_template import ImagingTemplate
from app.models.user import User
from app.schemas.imaging_template import (
    ImagingTemplateCreate,
    ImagingTemplateListResponse,
    ImagingTemplateResponse,
)
from app.services.audit_service import log_action


def _to_response(tpl: ImagingTemplate) -> ImagingTemplateResponse:
    creator_name = None
    if tpl.creator:
        creator_name = f"{tpl.creator.first_name} {tpl.creator.last_name}"
    return ImagingTemplateResponse(
        id=tpl.id,
        clinic_id=tpl.clinic_id,
        created_by=tpl.created_by,
        name=tpl.name,
        study_type=tpl.study_type,
        findings=tpl.findings or {},
        conclusion_items=tpl.conclusion_items or [],
        recommendations=tpl.recommendations,
        created_at=tpl.created_at,
        creator_name=creator_name,
    )


async def _get_or_404(
    db: AsyncSession, clinic_id: UUID, template_id: UUID
) -> ImagingTemplate:
    result = await db.execute(
        select(ImagingTemplate)
        .options(joinedload(ImagingTemplate.creator))
        .where(
            ImagingTemplate.id == template_id,
            ImagingTemplate.clinic_id == clinic_id,
        )
    )
    tpl = result.unique().scalar_one_or_none()
    if not tpl:
        raise NotFoundException("Plantilla de imagenología")
    return tpl


async def list_templates(
    db: AsyncSession,
    clinic_id: UUID,
    study_type: ImagingStudyType | None = None,
) -> ImagingTemplateListResponse:
    stmt = (
        select(ImagingTemplate)
        .options(joinedload(ImagingTemplate.creator))
        .where(ImagingTemplate.clinic_id == clinic_id)
        .order_by(ImagingTemplate.created_at.desc())
    )
    if study_type is not None:
        stmt = stmt.where(ImagingTemplate.study_type == study_type)
    result = await db.execute(stmt)
    items = result.unique().scalars().all()
    return ImagingTemplateListResponse(
        items=[_to_response(t) for t in items],
        total=len(items),
    )


async def create_template(
    db: AsyncSession,
    user: User,
    data: ImagingTemplateCreate,
    ip_address: str | None = None,
) -> ImagingTemplateResponse:
    tpl = ImagingTemplate(
        clinic_id=user.clinic_id,
        created_by=user.id,
        name=data.name.strip(),
        study_type=data.study_type,
        findings=data.findings,
        conclusion_items=data.conclusion_items,
        recommendations=data.recommendations,
    )
    db.add(tpl)
    await db.flush()

    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="imaging_template",
        entity_id=str(tpl.id),
        action="create",
        new_data={"name": tpl.name, "study_type": data.study_type.value},
        ip_address=ip_address,
    )

    tpl = await _get_or_404(db, user.clinic_id, tpl.id)
    return _to_response(tpl)


async def delete_template(
    db: AsyncSession,
    user: User,
    template_id: UUID,
    ip_address: str | None = None,
) -> None:
    tpl = await _get_or_404(db, user.clinic_id, template_id)
    await db.delete(tpl)
    await db.flush()

    await log_action(
        db,
        clinic_id=user.clinic_id,
        user_id=user.id,
        entity="imaging_template",
        entity_id=str(template_id),
        action="delete",
        ip_address=ip_address,
    )
