"""
Modelo Cie10Code — Catálogo de diagnósticos CIE-10 (OMS).

Tabla de referencia global (sin clinic_id). Se carga desde CSV
con el catálogo oficial en español.
"""

import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Cie10Code(Base):
    __tablename__ = "cie10_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True,
        comment="Código CIE-10: A00, A00.0, Z99.9, etc."
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Descripción en español del diagnóstico"
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Capítulo/categoría: Infecciosas, Oftalmología, etc."
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Permite desactivar códigos obsoletos sin borrarlos"
    )

    __table_args__ = (
        Index("idx_cie10_code", "code"),
        Index("idx_cie10_category", "category"),
        Index("idx_cie10_description_trgm", "description",
              postgresql_ops={"description": "gin_trgm_ops"},
              postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Cie10Code {self.code}: {self.description[:50]}>"
