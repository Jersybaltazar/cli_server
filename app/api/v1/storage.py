"""
Endpoints para subida/descarga de archivos via Cloudflare R2.
El backend genera presigned URLs; el browser sube/descarga directo a R2.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import require_role
from app.models.user import User, UserRole
from app.services import storage_service

router = APIRouter()

_ALL_ROLES = tuple(UserRole)


class PresignedUploadRequest(BaseModel):
    filename: str
    content_type: str
    folder: str = "labs"  # labs | records | invoices | vaccinations


class PresignedUploadResponse(BaseModel):
    upload_url: str   # PUT aquí desde el browser
    file_key: str     # guardar en DB
    public_url: str   # URL permanente para mostrar


@router.post("/presigned-upload", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    body: PresignedUploadRequest,
    user: User = Depends(require_role(*_ALL_ROLES)),
):
    """
    Genera una presigned PUT URL (válida 5 min) para que el browser suba
    un archivo directamente a Cloudflare R2 sin pasar por el backend.

    Flujo:
    1. Frontend llama este endpoint → recibe `upload_url` + `file_key` + `public_url`
    2. Frontend hace PUT a `upload_url` con el archivo binario + header `Content-Type`
    3. Frontend guarda `file_key` o `public_url` en el recurso correspondiente (lab order, etc.)
    """
    try:
        result = storage_service.generate_presigned_upload(
            clinic_id=str(user.clinic_id),
            filename=body.filename,
            content_type=body.content_type,
            folder=body.folder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return result


@router.get("/presigned-download")
async def get_presigned_download_url(
    file_key: str = Query(..., description="Clave del objeto en R2"),
    expires_in: int = Query(3600, ge=60, le=86400),
    user: User = Depends(require_role(*_ALL_ROLES)),
):
    """
    Genera una presigned GET URL para descargar un archivo privado de R2.
    Úsalo solo si el bucket NO es público.
    """
    try:
        url = storage_service.generate_presigned_download(
            file_key=file_key,
            expires_in=expires_in,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {"download_url": url, "expires_in": expires_in}
