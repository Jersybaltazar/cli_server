"""
Modelo MedicationCatalog — Catálogo local de medicamentos.

Tabla de referencia global (sin clinic_id). Sembrada inicialmente con
medicamentos del PNUME (Petitorio Nacional Único de Medicamentos
Esenciales) — Fase 2, Hito 2.2.

Búsqueda fuzzy con pg_trgm sobre `dci` y `commercial_name`.
"""

import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MedicationCatalog(Base):
    __tablename__ = "medication_catalog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Identificación ──────────────────────────────
    dci: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Denominación común internacional (DCI / IFA)"
    )
    commercial_name: Mapped[str | None] = mapped_column(
        String(255),
        comment="Nombre comercial principal (opcional)"
    )

    # ── Forma farmacéutica ──────────────────────────
    form: Mapped[str | None] = mapped_column(
        String(80),
        comment="Forma farmacéutica: tableta, jarabe, ampolla, crema, etc."
    )
    concentration: Mapped[str | None] = mapped_column(
        String(80),
        comment="Concentración: 500 mg, 250 mg/5 mL, 1 g, etc."
    )
    presentation: Mapped[str | None] = mapped_column(
        String(160),
        comment="Presentación textual lista para imprimir en receta"
    )

    # ── Vía de administración ───────────────────────
    route: Mapped[str | None] = mapped_column(
        String(40),
        comment="oral, IM, IV, SC, tópica, oftálmica, vaginal, etc."
    )

    # ── Clasificación regulatoria ───────────────────
    atc_code: Mapped[str | None] = mapped_column(
        String(10),
        comment="Código ATC (Anatomical Therapeutic Chemical) — opcional"
    )
    therapeutic_group: Mapped[str | None] = mapped_column(
        String(120),
        comment="Grupo terapéutico (ej: Antibiótico betalactámico)"
    )
    is_essential: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True si pertenece al PNUME"
    )
    is_controlled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True si es psicotrópico/estupefaciente (lista IIA / IIIA-C)"
    )
    controlled_list: Mapped[str | None] = mapped_column(
        String(20),
        comment="Lista DIGEMID: IIA, IIIA, IIIB, IIIC, IV, V, VI"
    )

    # ── Notas clínicas ──────────────────────────────
    notes: Mapped[str | None] = mapped_column(
        Text,
        comment="Advertencias, contraindicaciones notables (texto libre)"
    )

    # ── Estado ──────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Permite desactivar entradas obsoletas sin borrarlas"
    )

    __table_args__ = (
        Index("idx_medication_dci", "dci"),
        Index("idx_medication_controlled", "is_controlled"),
        Index("idx_medication_essential", "is_essential"),
        Index(
            "idx_medication_dci_trgm", "dci",
            postgresql_ops={"dci": "gin_trgm_ops"},
            postgresql_using="gin",
        ),
        Index(
            "idx_medication_commercial_trgm", "commercial_name",
            postgresql_ops={"commercial_name": "gin_trgm_ops"},
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return f"<MedicationCatalog {self.dci} {self.concentration or ''}>"
