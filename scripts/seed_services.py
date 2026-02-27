"""
Seed del tarifario de servicios CEM desde CSV.

Uso:
    python scripts/seed_services.py <clinic_id>

Lee data/service_tariff.csv y hace upsert por (clinic_id, name).
Si el servicio ya existe, actualiza precio/costo/categoría.
Si no existe, lo crea.
"""

import asyncio
import csv
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_engine, AsyncSessionLocal  # noqa: E402
from app.models.service import Service, ServiceCategory  # noqa: E402


CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "service_tariff.csv"

CATEGORY_MAP = {
    "consultation": ServiceCategory.CONSULTATION,
    "ecography": ServiceCategory.ECOGRAPHY,
    "procedure": ServiceCategory.PROCEDURE,
    "lab_external": ServiceCategory.LAB_EXTERNAL,
    "surgery": ServiceCategory.SURGERY,
    "cpn": ServiceCategory.CPN,
    "vaccination": ServiceCategory.VACCINATION,
    "other": ServiceCategory.OTHER,
}


async def seed_services(clinic_id: UUID) -> None:
    """Lee el CSV y hace upsert de servicios para la clínica indicada."""
    if not CSV_PATH.exists():
        print(f"ERROR: No se encontró el archivo {CSV_PATH}")
        sys.exit(1)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Leyendo {len(rows)} servicios desde {CSV_PATH.name}...")

    async with AsyncSessionLocal() as db:
        created = 0
        updated = 0

        for row in rows:
            name = row["name"].strip()
            code = row["code"].strip()
            category = CATEGORY_MAP.get(row["category"].strip(), ServiceCategory.OTHER)
            price = Decimal(row["price"].strip())
            cost_price = Decimal(row["cost_price"].strip())
            duration_minutes = int(row["duration_minutes"].strip())
            color = row.get("color", "").strip() or None

            # Buscar si ya existe por nombre + clínica
            result = await db.execute(
                select(Service).where(
                    Service.clinic_id == clinic_id,
                    Service.name == name,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Actualizar campos
                existing.code = code
                existing.category = category
                existing.price = price
                existing.cost_price = cost_price
                existing.duration_minutes = duration_minutes
                if color:
                    existing.color = color
                updated += 1
            else:
                # Crear nuevo
                service = Service(
                    clinic_id=clinic_id,
                    code=code,
                    name=name,
                    category=category,
                    price=price,
                    cost_price=cost_price,
                    duration_minutes=duration_minutes,
                    color=color,
                    is_active=True,
                )
                db.add(service)
                created += 1

        await db.commit()
        print(f"Seed completado: {created} creados, {updated} actualizados.")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_services.py <clinic_id>")
        print("  clinic_id: UUID de la clínica donde crear los servicios")
        sys.exit(1)

    try:
        clinic_id = UUID(sys.argv[1])
    except ValueError:
        print(f"ERROR: '{sys.argv[1]}' no es un UUID válido")
        sys.exit(1)

    asyncio.run(seed_services(clinic_id))


if __name__ == "__main__":
    main()
