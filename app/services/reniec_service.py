"""
Servicio unificado de consultas a json.pe (RENIEC DNI + SUNAT RUC).
Incluye cache en memoria (TTL) para evitar consultas repetidas.
"""

import time
from typing import Optional

import httpx

from app.config import get_settings
from app.core.exceptions import NotFoundException, ValidationException

settings = get_settings()

# ── Cache en memoria ─────────────────────────────────
# Formato: {key: {"data": {...}, "timestamp": float}}
_cache: dict[str, dict] = {}
_CACHE_TTL_SECONDS: int = 3600  # 1 hora


def _cache_get(key: str) -> Optional[dict]:
    """Obtiene un resultado del cache si existe y no ha expirado."""
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.time() - entry["timestamp"] > _CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return entry["data"]


def _cache_set(key: str, data: dict) -> None:
    """Guarda un resultado en el cache."""
    _cache[key] = {"data": data, "timestamp": time.time()}


async def _jsonpe_post(endpoint: str, body: dict) -> dict:
    """
    Ejecuta una petición POST a la API de json.pe.
    Retorna el dict del campo 'data' de la respuesta.
    """
    url = f"{settings.JSONPE_API_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {settings.JSONPE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.TimeoutException:
        raise ValidationException(
            f"Timeout al consultar json.pe ({endpoint}). Intente nuevamente."
        )
    except httpx.RequestError as exc:
        raise ValidationException(
            f"Error de conexión con json.pe: {str(exc)}"
        )

    if response.status_code == 404:
        raise NotFoundException(
            endpoint.upper(),
            f"No se encontró información para la consulta",
        )

    if response.status_code != 200:
        raise ValidationException(
            f"Error al consultar json.pe ({endpoint}) — status {response.status_code}"
        )

    payload = response.json()

    if not payload.get("success"):
        msg = payload.get("message", "Error desconocido")
        raise ValidationException(f"json.pe respondió con error: {msg}")

    return payload.get("data", {})


# ─────────────────────────────────────────────────────
# Consulta DNI (RENIEC)
# ─────────────────────────────────────────────────────


async def consultar_dni(dni: str) -> dict:
    """
    Consulta un DNI de 8 dígitos en json.pe (RENIEC).

    Returns:
        dict con: dni, nombres, apellido_paterno, apellido_materno,
                  nombre_completo, codigo_verificacion.
    """
    if not dni or not dni.isdigit() or len(dni) != 8:
        raise ValidationException(
            "El DNI debe ser exactamente 8 dígitos numéricos"
        )

    # Cache
    cached = _cache_get(f"dni:{dni}")
    if cached is not None:
        return cached

    data = await _jsonpe_post("dni", {"dni": dni})

    result = {
        "dni": data.get("numero", dni),
        "nombres": data.get("nombres", ""),
        "apellido_paterno": data.get("apellido_paterno", ""),
        "apellido_materno": data.get("apellido_materno", ""),
        "nombre_completo": data.get("nombre_completo", ""),
        "codigo_verificacion": data.get("codigo_verificacion"),
    }

    _cache_set(f"dni:{dni}", result)
    return result


# ─────────────────────────────────────────────────────
# Consulta RUC (SUNAT)
# ─────────────────────────────────────────────────────


async def consultar_ruc(ruc: str) -> dict:
    """
    Consulta un RUC de 11 dígitos en json.pe (SUNAT).

    Returns:
        dict con: ruc, nombre_o_razon_social, estado, condicion,
                  direccion, departamento, provincia, distrito, etc.
    """
    if not ruc or not ruc.isdigit() or len(ruc) != 11:
        raise ValidationException(
            "El RUC debe ser exactamente 11 dígitos numéricos"
        )

    # Cache
    cached = _cache_get(f"ruc:{ruc}")
    if cached is not None:
        return cached

    data = await _jsonpe_post("ruc", {"ruc": ruc})

    result = {
        "ruc": data.get("ruc", ruc),
        "nombre_o_razon_social": data.get("nombre_o_razon_social", ""),
        "estado": data.get("estado", ""),
        "condicion": data.get("condicion", ""),
        "direccion": data.get("direccion", ""),
        "direccion_completa": data.get("direccion_completa", ""),
        "departamento": data.get("departamento", ""),
        "provincia": data.get("provincia", ""),
        "distrito": data.get("distrito", ""),
        "ubigeo_sunat": data.get("ubigeo_sunat", ""),
    }

    _cache_set(f"ruc:{ruc}", result)
    return result
