"""
Endpoints de consulta RENIEC (DNI) y SUNAT (RUC) via json.pe.
"""

from fastapi import APIRouter, Path

from app.schemas.reniec import ReniecDNIResponse, SunatRUCResponse
from app.services.reniec_service import consultar_dni, consultar_ruc

router = APIRouter()


@router.get(
    "/dni/{dni}",
    response_model=ReniecDNIResponse,
    summary="Consultar DNI en RENIEC",
    description=(
        "Consulta un DNI de 8 dígitos en RENIEC vía json.pe. "
        "Resultados cacheados en memoria (1 hora)."
    ),
)
async def get_dni_info(
    dni: str = Path(
        ...,
        min_length=8,
        max_length=8,
        pattern=r"^\d{8}$",
        description="DNI de 8 dígitos",
        examples=["27427864"],
    ),
) -> ReniecDNIResponse:
    """Consulta información de un DNI en RENIEC."""
    result = await consultar_dni(dni)
    return ReniecDNIResponse(**result)


@router.get(
    "/ruc/{ruc}",
    response_model=SunatRUCResponse,
    summary="Consultar RUC en SUNAT",
    description=(
        "Consulta un RUC de 11 dígitos en SUNAT vía json.pe. "
        "Resultados cacheados en memoria (1 hora)."
    ),
)
async def get_ruc_info(
    ruc: str = Path(
        ...,
        min_length=11,
        max_length=11,
        pattern=r"^\d{11}$",
        description="RUC de 11 dígitos",
        examples=["20552103816"],
    ),
) -> SunatRUCResponse:
    """Consulta información de un RUC en SUNAT."""
    result = await consultar_ruc(ruc)
    return SunatRUCResponse(**result)
