from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.models.lab_order import LabOrderStatus, LabStudyType
from app.schemas.lab import (
    LabOrderCreate, LabOrderUpdate, LabOrderResponse,
    LabResultCreate, LabResultResponse, LabDashboardStats,
    LabOrderListResponse, PresignedUploadRequest, PresignedUploadResponse,
)
from app.services import lab_service
from app.services import storage_service
from app.services.pdf_service import render_lab_order_pdf, render_lab_result_pdf
from app.auth.dependencies import require_role

router = APIRouter()

@router.post("/orders", response_model=LabOrderResponse, status_code=201)
async def create_lab_order(
    data: LabOrderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA))
):
    """Crea una nueva orden de laboratorio (Admin o Doctor)."""
    return await lab_service.create_order(db, user.clinic_id, user.id, data)

@router.get("/orders", response_model=LabOrderListResponse)
async def list_lab_orders(
    status: LabOrderStatus | None = Query(None),
    study_type: LabStudyType | None = Query(None),
    patient_id: UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Lista las órdenes de laboratorio de la clínica con filtros."""
    return await lab_service.list_orders(
        db, user.clinic_id, status, study_type, patient_id, date_from, date_to, page, size
    )

@router.get("/dashboard", response_model=LabDashboardStats)
async def get_lab_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Obtiene estadísticas generales del módulo de laboratorio."""
    return await lab_service.get_dashboard_stats(db, user.clinic_id)

@router.get("/orders/{order_id}", response_model=LabOrderResponse)
async def get_lab_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Obtiene el detalle de una orden específica."""
    return await lab_service.get_order(db, user.clinic_id, order_id)

@router.patch("/orders/{order_id}", response_model=LabOrderResponse)
async def update_lab_order(
    order_id: UUID,
    data: LabOrderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA, UserRole.RECEPTIONIST))
):
    """Actualiza el estado o datos de tracking de una orden."""
    return await lab_service.update_order(db, user.clinic_id, order_id, data, user.id)

@router.post("/orders/{order_id}/result", response_model=LabResultResponse)
async def register_lab_result(
    order_id: UUID,
    data: LabResultCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.OBSTETRA))
):
    """Registra el resultado detallado de una orden (Admin o Doctor)."""
    return await lab_service.register_result(db, user.clinic_id, order_id, user.id, data)

@router.get(
    "/orders/{order_id}/pdf",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_lab_order_pdf(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Descarga la orden de laboratorio en formato PDF."""
    order = await lab_service.get_order(db, user.clinic_id, order_id)
    pdf_bytes = render_lab_order_pdf(
        order=order,
        patient=order.patient,
        doctor=order.doctor,
        clinic=order.clinic,
    )
    filename = f"orden-lab-{order.lab_code or order.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/orders/{order_id}/result/pdf",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_lab_result_pdf(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Descarga el resultado de laboratorio en formato PDF."""
    order = await lab_service.get_order(db, user.clinic_id, order_id)
    if not order.result:
        raise HTTPException(status_code=404, detail="Esta orden aún no tiene resultado registrado")
    pdf_bytes = render_lab_result_pdf(
        order=order,
        result=order.result,
        patient=order.patient,
        doctor=order.doctor,
        clinic=order.clinic,
    )
    filename = f"resultado-lab-{order.lab_code or order.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/files/presigned-upload", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    data: PresignedUploadRequest,
    user: User = Depends(get_current_user),
):
    """
    Genera una presigned PUT URL para subir un archivo (PDF/imagen) directamente
    desde el browser a Cloudflare R2. El archivo nunca pasa por el backend.

    Flujo:
      1. Frontend llama este endpoint con { filename, content_type }
      2. Recibe { upload_url, file_key, public_url }
      3. Frontend hace PUT a upload_url con el archivo binario
      4. Frontend guarda { name, url: public_url, key: file_key } en el resultado
    """
    try:
        result = storage_service.generate_presigned_upload(
            clinic_id=str(user.clinic_id),
            filename=data.filename,
            content_type=data.content_type,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/patients/{patient_id}/history", response_model=list[LabOrderResponse])
async def get_patient_lab_history(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Obtiene el historial de laboratorio de un paciente específico."""
    return await lab_service.get_patient_history(db, user.clinic_id, patient_id)
