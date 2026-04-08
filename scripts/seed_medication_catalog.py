"""
Script para sembrar el catálogo de medicamentos (Fase 2 — Hito 2.2).

Carga el JSON `app/seeds/medication_catalog_seed.json` (~120 entradas
representativas del PNUME y de uso frecuente en gineco-obstetricia y
atención primaria) en la tabla `medication_catalog`.

Uso:
    python scripts/seed_medication_catalog.py
    python scripts/seed_medication_catalog.py --clear
    python scripts/seed_medication_catalog.py --seed app/seeds/otro.json
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models.medication_catalog import MedicationCatalog  # noqa: E402


DEFAULT_SEED = (
    Path(__file__).resolve().parent.parent
    / "app" / "seeds" / "medication_catalog_seed.json"
)


async def seed(seed_path: Path, clear: bool = False) -> None:
    if not seed_path.exists():
        print(f"ERROR: No se encontró el seed: {seed_path}")
        sys.exit(1)

    with open(seed_path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    print(f"Leídas {len(rows)} entradas del seed")

    async with async_session_factory() as session:
        async with session.begin():
            if clear:
                await session.execute(text("DELETE FROM medication_catalog"))
                print("Tabla medication_catalog vaciada")

            existing = await session.execute(
                select(MedicationCatalog.dci, MedicationCatalog.concentration)
            )
            seen = {(d, c) for d, c in existing.fetchall()}

            inserted = 0
            skipped = 0
            for row in rows:
                key = (row.get("dci"), row.get("concentration"))
                if key in seen:
                    skipped += 1
                    continue
                med = MedicationCatalog(
                    dci=row["dci"],
                    commercial_name=row.get("commercial_name"),
                    form=row.get("form"),
                    concentration=row.get("concentration"),
                    presentation=row.get("presentation"),
                    route=row.get("route"),
                    atc_code=row.get("atc_code"),
                    therapeutic_group=row.get("therapeutic_group"),
                    is_essential=bool(row.get("is_essential", False)),
                    is_controlled=bool(row.get("is_controlled", False)),
                    controlled_list=row.get("controlled_list"),
                    notes=row.get("notes"),
                )
                session.add(med)
                inserted += 1
                seen.add(key)

            print(f"Insertados: {inserted} · Omitidos (ya existían): {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed catálogo de medicamentos")
    parser.add_argument(
        "--seed", type=Path, default=DEFAULT_SEED,
        help="Ruta al JSON del seed",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Borrar todo el catálogo antes de insertar",
    )
    args = parser.parse_args()

    asyncio.run(seed(args.seed, clear=args.clear))


if __name__ == "__main__":
    main()
