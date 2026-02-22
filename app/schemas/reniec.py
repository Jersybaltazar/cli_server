"""
Schemas Pydantic para consultas DNI (RENIEC) y RUC (SUNAT) via json.pe.
"""

from pydantic import BaseModel, Field


class ReniecDNIResponse(BaseModel):
    """Respuesta de consulta DNI a RENIEC via json.pe."""

    dni: str = Field(..., description="Número de DNI consultado", examples=["27427864"])
    nombres: str = Field(..., description="Nombres de la persona", examples=["JOSE PEDRO"])
    apellido_paterno: str = Field(..., description="Apellido paterno", examples=["CASTILLO"])
    apellido_materno: str = Field(..., description="Apellido materno", examples=["TERRONES"])
    nombre_completo: str = Field(
        ...,
        description="Nombre completo (apellidos, nombres)",
        examples=["CASTILLO TERRONES, JOSE PEDRO"],
    )
    codigo_verificacion: int | None = Field(
        None, description="Código de verificación del DNI"
    )


class SunatRUCResponse(BaseModel):
    """Respuesta de consulta RUC a SUNAT via json.pe."""

    ruc: str = Field(..., description="Número de RUC consultado", examples=["20552103816"])
    nombre_o_razon_social: str = Field(
        ...,
        description="Razón social o nombre del contribuyente",
        examples=["AGROLIGHT PERU S.A.C."],
    )
    estado: str = Field(..., description="Estado del contribuyente", examples=["ACTIVO"])
    condicion: str = Field(..., description="Condición del contribuyente", examples=["HABIDO"])
    direccion: str = Field("", description="Dirección fiscal")
    direccion_completa: str = Field("", description="Dirección fiscal completa con ubigeo")
    departamento: str = Field("", description="Departamento", examples=["LIMA"])
    provincia: str = Field("", description="Provincia", examples=["LIMA"])
    distrito: str = Field("", description="Distrito", examples=["SANTA ANITA"])
    ubigeo_sunat: str = Field("", description="Código de ubigeo SUNAT", examples=["150137"])
