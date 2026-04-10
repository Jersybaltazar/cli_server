"""
Servicio de detección de interacciones medicamentosas (DDI).

Fase 2, Hito 2.4. Verifica:
  1) Intra-receta: entre items de la misma receta.
  2) Cross-receta: contra recetas activas (firmadas, no vencidas) del
     mismo paciente.

Búsqueda por DCI normalizado (lowercase). La tabla drug_interactions
almacena pares (drug_a, drug_b) en orden alfabético.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drug_interaction import DrugInteraction
from app.models.medication_catalog import MedicationCatalog
from app.models.prescription import Prescription, PrescriptionItem
from app.schemas.drug_interaction import DDICheckResponse, DrugInteractionAlert


async def check_interactions(
    db: AsyncSession,
    *,
    patient_id: UUID,
    items: list[dict],
    exclude_prescription_id: UUID | None = None,
) -> DDICheckResponse:
    """
    Verifica interacciones para un conjunto de items de receta.

    `items` es una lista de dicts con keys: medication (str), medication_id (UUID|None), index (int).

    Retorna DDICheckResponse con las alertas encontradas.
    """
    if not items:
        return DDICheckResponse(alerts=[], total=0)

    # ── 1. Resolver DCI para cada item ─────────────────
    dci_list = await _resolve_dci_names(db, items)
    # dci_list: list[tuple[int, str]]  → (item_index, dci_lowercase)

    if len(dci_list) < 1:
        return DDICheckResponse(alerts=[], total=0)

    # ── 2. Recopilar DCIs de recetas activas del paciente ──
    active_dcis = await _get_active_patient_dcis(
        db, patient_id=patient_id, exclude_id=exclude_prescription_id
    )

    # ── 3. Construir todos los pares a verificar ───────
    all_dcis: list[tuple[int | None, str]] = list(dci_list) + [
        (None, d) for d in active_dcis
    ]

    pairs_to_check: set[tuple[str, str]] = set()
    pair_indices: dict[tuple[str, str], tuple[int | None, int | None]] = {}

    for i in range(len(all_dcis)):
        for j in range(i + 1, len(all_dcis)):
            idx_a, dci_a = all_dcis[i]
            idx_b, dci_b = all_dcis[j]
            if dci_a == dci_b:
                continue
            pair = (dci_a, dci_b) if dci_a <= dci_b else (dci_b, dci_a)
            if pair not in pairs_to_check:
                pairs_to_check.add(pair)
                pair_indices[pair] = (idx_a, idx_b)

    if not pairs_to_check:
        return DDICheckResponse(alerts=[], total=0)

    # ── 4. Consultar interacciones en batch ────────────
    conditions = [
        (DrugInteraction.drug_a == a) & (DrugInteraction.drug_b == b)
        for a, b in pairs_to_check
    ]
    result = await db.execute(
        select(DrugInteraction).where(or_(*conditions))
    )
    found = result.scalars().all()

    # ── 5. Mapear resultados ───────────────────────────
    alerts: list[DrugInteractionAlert] = []
    for di in found:
        pair = (di.drug_a, di.drug_b)
        idx_a, idx_b = pair_indices.get(pair, (None, None))
        alerts.append(
            DrugInteractionAlert(
                interaction_id=di.id,
                drug_a=di.drug_a,
                drug_b=di.drug_b,
                severity=di.severity,
                description=di.description,
                recommendation=di.recommendation,
                item_index_a=idx_a,
                item_index_b=idx_b,
            )
        )

    # Ordenar: contraindicated primero, luego major, moderate, minor
    severity_order = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 9))

    return DDICheckResponse(
        alerts=alerts,
        has_contraindicated=any(a.severity == "contraindicated" for a in alerts),
        has_major=any(a.severity == "major" for a in alerts),
        total=len(alerts),
    )


# ── Helpers ────────────────────────────────────────────


async def _resolve_dci_names(
    db: AsyncSession,
    items: list[dict],
) -> list[tuple[int, str]]:
    """
    Para cada item, resuelve su DCI normalizado.
    Si tiene medication_id → busca en catálogo. Si no → usa medication text.
    """
    results: list[tuple[int, str]] = []
    catalog_ids = [
        (it["index"], it["medication_id"])
        for it in items
        if it.get("medication_id")
    ]

    # Batch lookup del catálogo
    catalog_dcis: dict[str, str] = {}
    if catalog_ids:
        ids = [mid for _, mid in catalog_ids]
        rows = await db.execute(
            select(MedicationCatalog.id, MedicationCatalog.dci).where(
                MedicationCatalog.id.in_(ids)
            )
        )
        for mid, dci in rows.all():
            catalog_dcis[str(mid)] = dci.strip().lower()

    for it in items:
        idx = it["index"]
        mid = it.get("medication_id")
        if mid and str(mid) in catalog_dcis:
            results.append((idx, catalog_dcis[str(mid)]))
        else:
            name = (it.get("medication") or "").strip().lower()
            if name:
                results.append((idx, name))

    return results


async def _get_active_patient_dcis(
    db: AsyncSession,
    *,
    patient_id: UUID,
    exclude_id: UUID | None = None,
) -> list[str]:
    """
    Obtiene los DCIs de las recetas activas del paciente:
    - Firmadas (signed_at IS NOT NULL)
    - No vencidas: created_at >= 30 días atrás (o valid_until >= hoy)
    """
    cutoff = date.today() - timedelta(days=30)
    query = (
        select(PrescriptionItem.medication, PrescriptionItem.medication_id)
        .join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
        .where(
            Prescription.patient_id == patient_id,
            Prescription.signed_at.isnot(None),
            or_(
                Prescription.valid_until >= date.today(),
                Prescription.created_at >= cutoff,
            ),
        )
    )
    if exclude_id:
        query = query.where(Prescription.id != exclude_id)

    result = await db.execute(query)
    rows = result.all()

    # Resolver DCIs: si tienen medication_id, consultar catálogo
    dcis: list[str] = []
    catalog_ids = [mid for _, mid in rows if mid is not None]
    catalog_dcis: dict[str, str] = {}
    if catalog_ids:
        cat_result = await db.execute(
            select(MedicationCatalog.id, MedicationCatalog.dci).where(
                MedicationCatalog.id.in_(catalog_ids)
            )
        )
        for mid, dci in cat_result.all():
            catalog_dcis[str(mid)] = dci.strip().lower()

    for med_name, med_id in rows:
        if med_id and str(med_id) in catalog_dcis:
            dcis.append(catalog_dcis[str(med_id)])
        else:
            name = (med_name or "").strip().lower()
            if name:
                dcis.append(name)

    return list(set(dcis))
