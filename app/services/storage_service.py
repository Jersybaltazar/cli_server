"""
Servicio de almacenamiento de archivos usando Cloudflare R2 (S3-compatible).
Genera presigned URLs para que el browser suba archivos directamente a R2
sin pasar por el backend.
"""

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from uuid import uuid4
from datetime import datetime, timezone

from app.config import get_settings

settings = get_settings()

# Tipos MIME permitidos
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

# Tamaño máximo: 20 MB
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def _get_r2_client():
    """Crea y retorna el cliente boto3 apuntando a Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def generate_presigned_upload(
    clinic_id: str,
    filename: str,
    content_type: str,
    folder: str = "labs",
    expires_in: int = 300,
) -> dict:
    """
    Genera una presigned PUT URL para subir un archivo directamente desde el browser a R2.

    Retorna:
        upload_url  — URL donde el browser hace PUT (expira en `expires_in` segundos)
        file_key    — Clave del objeto en R2 (para guardar en DB)
        public_url  — URL pública permanente para acceder al archivo
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(
            f"Tipo de archivo no permitido: {content_type}. "
            f"Se aceptan: PDF, JPG, PNG, GIF, WEBP."
        )

    if not settings.R2_ENDPOINT_URL or not settings.R2_ACCESS_KEY_ID:
        raise RuntimeError(
            "Cloudflare R2 no está configurado. "
            "Completa R2_ENDPOINT_URL, R2_ACCESS_KEY_ID y R2_SECRET_ACCESS_KEY en .env"
        )

    # Sanitizar nombre de archivo
    safe_filename = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in filename
    )

    # Clave organizada por clínica y fecha: labs/{clinic_id}/2026/03/{uuid}_{filename}
    now = datetime.now(timezone.utc)
    file_key = (
        f"{folder}/{clinic_id}/{now.year}/{now.month:02d}"
        f"/{uuid4().hex}_{safe_filename}"
    )

    try:
        s3 = _get_r2_client()
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": file_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Error generando presigned URL: {exc}") from exc

    public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{file_key}"

    return {
        "upload_url": upload_url,
        "file_key": file_key,
        "public_url": public_url,
    }


def generate_presigned_download(file_key: str, expires_in: int = 3600) -> str:
    """
    Genera una presigned GET URL para descargar un archivo privado de R2.
    Útil si el bucket NO es público.
    """
    try:
        s3 = _get_r2_client()
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": file_key,
            },
            ExpiresIn=expires_in,
        )
        return url
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Error generando download URL: {exc}") from exc


def delete_file(file_key: str) -> None:
    """Elimina un objeto de R2 por su clave."""
    try:
        s3 = _get_r2_client()
        s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=file_key)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Error eliminando archivo: {exc}") from exc
