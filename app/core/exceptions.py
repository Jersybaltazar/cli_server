"""
Excepciones HTTP personalizadas para la API.
"""

from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    """Error de credenciales inválidas (401)."""

    def __init__(self, detail: str = "Credenciales inválidas"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(HTTPException):
    """Error de permisos insuficientes (403)."""

    def __init__(self, detail: str = "No tiene permisos para realizar esta acción"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class NotFoundException(HTTPException):
    """Recurso no encontrado (404)."""

    def __init__(self, resource: str = "Recurso", detail: str | None = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{resource} no encontrado",
        )


class ConflictException(HTTPException):
    """Conflicto de datos (409) — ej: email o DNI duplicado."""

    def __init__(self, detail: str = "El recurso ya existe"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class ValidationException(HTTPException):
    """Error de validación de negocio (422)."""

    def __init__(self, detail: str = "Error de validación"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class TenantException(HTTPException):
    """Error de contexto multi-tenant (400)."""

    def __init__(self, detail: str = "Contexto de clínica no disponible"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
