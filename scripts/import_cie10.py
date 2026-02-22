"""
Script para importar el catálogo CIE-10 desde CSV a la tabla cie10_codes.

Uso:
    python scripts/import_cie10.py
    python scripts/import_cie10.py --csv data/cie10_catalog.csv
    python scripts/import_cie10.py --clear  # borra todo antes de importar

Requisitos:
    - La migración h8i9j0k1l2m3 debe estar aplicada
    - El archivo CSV debe tener columnas: code,description,category
"""

import argparse
import csv
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from sqlalchemy import text, select, func
from app.database import async_session_factory
from app.models.cie10 import Cie10Code


DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "cie10_catalog.csv"


async def import_cie10(csv_path: Path, clear: bool = False) -> None:
    if not csv_path.exists():
        print(f"ERROR: No se encontró el archivo CSV: {csv_path}")
        sys.exit(1)

    # Leer CSV
    entries: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("code", "").strip().upper()
            description = row.get("description", "").strip()
            category = row.get("category", "").strip()

            if not code or not description:
                continue

            entries.append({
                "code": code,
                "description": description,
                "category": category or "Sin categoría",
            })

    print(f"Leídos {len(entries)} códigos del CSV")

    async with async_session_factory() as session:
        async with session.begin():
            if clear:
                await session.execute(text("DELETE FROM cie10_codes"))
                print("Tabla cie10_codes vaciada")

            # Contar existentes
            count_result = await session.execute(
                select(func.count()).select_from(Cie10Code)
            )
            existing_count = count_result.scalar() or 0
            print(f"Códigos existentes en BD: {existing_count}")

            # Obtener códigos ya existentes
            existing_result = await session.execute(
                select(Cie10Code.code)
            )
            existing_codes = {row[0] for row in existing_result.fetchall()}

            # Insertar nuevos (skip duplicados)
            inserted = 0
            skipped = 0
            for entry in entries:
                if entry["code"] in existing_codes:
                    skipped += 1
                    continue

                session.add(Cie10Code(
                    code=entry["code"],
                    description=entry["description"],
                    category=entry["category"],
                ))
                existing_codes.add(entry["code"])
                inserted += 1

            print(f"Insertados: {inserted}")
            print(f"Omitidos (ya existían): {skipped}")

        # Verificar total final
        async with session.begin():
            final_count = await session.execute(
                select(func.count()).select_from(Cie10Code)
            )
            total = final_count.scalar() or 0
            print(f"Total códigos en BD: {total}")

    print("Importación completada")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importar catálogo CIE-10 a la BD")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Ruta al CSV")
    parser.add_argument("--clear", action="store_true", help="Vaciar tabla antes de importar")
    args = parser.parse_args()

    asyncio.run(import_cie10(args.csv, args.clear))
