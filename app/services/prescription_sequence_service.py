"""
Servicio de numeración correlativa de recetas.

Fase 2 — Hito 2.1. Genera seriales únicos por clínica/año/tipo, usando
SELECT FOR UPDATE para evitar colisiones en concurrencia. El serial se asigna
al firmar la receta (no en draft) para no dejar huecos en la numeración —
relevante para auditoría DIGEMID.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prescription_sequence import PrescriptionSequence


_PREFIX_MAP: dict[str, str] = {
    "common": "RX",
    "controlled": "RXC",
}


async def next_serial(
    db: AsyncSession,
    clinic_id: UUID,
    kind: str = "common",
) -> str:
    """
    Genera el siguiente serial correlativo para la clínica/tipo/año actual.

    Formato: ``{PREFIX}-{YYYY}-{NNNNNN}`` — ej ``RX-2026-000123``.

    Usa ``SELECT … FOR UPDATE`` sobre la fila ``prescription_sequences`` para
    serializar las concurrencias dentro de la misma transacción.
    """
    prefix = _PREFIX_MAP.get(kind)
    if prefix is None:
        raise ValueError(f"Tipo de receta desconocido para serial: {kind}")

    year = datetime.now().year

    result = await db.execute(
        select(PrescriptionSequence)
        .where(
            PrescriptionSequence.clinic_id == clinic_id,
            PrescriptionSequence.kind == kind,
            PrescriptionSequence.year == year,
        )
        .with_for_update()
    )
    seq = result.scalar_one_or_none()

    if seq is None:
        seq = PrescriptionSequence(
            clinic_id=clinic_id,
            kind=kind,
            year=year,
            last_number=0,
        )
        db.add(seq)
        await db.flush()

    seq.last_number += 1
    await db.flush()

    return f"{prefix}-{year}-{seq.last_number:06d}"
