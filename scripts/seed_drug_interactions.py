"""
Script para sembrar las interacciones medicamentosas (Fase 2 — Hito 2.4).

Carga el JSON `app/seeds/drug_interactions_seed.json` en la tabla
`drug_interactions`. Cada par se normaliza a lowercase y se almacena
en orden alfabético (drug_a < drug_b) para evitar duplicados.

Uso:
    python scripts/seed_drug_interactions.py
    python scripts/seed_drug_interactions.py --clear
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models.drug_interaction import DrugInteraction  # noqa: E402


DEFAULT_SEED = (
    Path(__file__).resolve().parent.parent
    / "app" / "seeds" / "drug_interactions_seed.json"
)


def _normalize_pair(a: str, b: str) -> tuple[str, str]:
    """Retorna el par en orden alfabético, lowercase."""
    a, b = a.strip().lower(), b.strip().lower()
    return (a, b) if a <= b else (b, a)


async def seed(seed_path: Path, clear: bool = False) -> None:
    if not seed_path.exists():
        print(f"ERROR: No se encontró el seed: {seed_path}")
        sys.exit(1)

    with open(seed_path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    print(f"Leídas {len(rows)} interacciones del seed")

    async with async_session_factory() as session:
        async with session.begin():
            if clear:
                await session.execute(text("DELETE FROM drug_interactions"))
                print("Tabla drug_interactions vaciada")

            existing = await session.execute(
                select(DrugInteraction.drug_a, DrugInteraction.drug_b)
            )
            seen = {(a, b) for a, b in existing.fetchall()}

            inserted = 0
            skipped = 0
            for row in rows:
                a, b = _normalize_pair(row["drug_a"], row["drug_b"])
                if (a, b) in seen:
                    skipped += 1
                    continue
                di = DrugInteraction(
                    drug_a=a,
                    drug_b=b,
                    severity=row["severity"],
                    description=row["description"],
                    recommendation=row.get("recommendation"),
                )
                session.add(di)
                inserted += 1
                seen.add((a, b))

            print(f"Insertados: {inserted} · Omitidos (ya existían): {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed interacciones medicamentosas")
    parser.add_argument(
        "--seed", type=Path, default=DEFAULT_SEED,
        help="Ruta al JSON del seed",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Borrar toda la tabla antes de insertar",
    )
    args = parser.parse_args()

    asyncio.run(seed(args.seed, clear=args.clear))


if __name__ == "__main__":
    main()
