"""
Seed de paquetes CPN para CEM Huánuco.

Uso:
    python scripts/seed_cpn_packages.py <clinic_id>

Crea dos paquetes CPN predefinidos con sus ítems de servicio.
Si el paquete ya existe (por nombre), lo omite.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import async_session_factory  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.service_package import PackageItem, ServicePackage  # noqa: E402


# ── Definición de paquetes ───────────────


PACKAGES = [
    {
        "name": "Paquete CPN A — Completo desde 6 semanas",
        "description": (
            "Control prenatal integral desde las 6 semanas. "
            "Incluye 8 consultas obstétricas, ecografías genética y morfológica, "
            "3 ecografías de rutina y panel de laboratorio."
        ),
        "total_price": Decimal("1500.00"),
        "valid_from_week": 6,
        "auto_schedule": True,
        "items": [
            # 8 consultas CPN en semanas específicas
            {"service_name": "Control Prenatal", "quantity": 1, "week": 8},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 12, "desc": "CPN + Eco genética"},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 16},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 20, "desc": "CPN + Eco morfológica"},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 24},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 28},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 32},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 36},
            # Ecografías
            {"service_name": "Ecografía Genética (11-14 sem)", "quantity": 1, "week": 12},
            {"service_name": "Ecografía Morfológica", "quantity": 1, "week": 20},
            {"service_name": "Ecografía Obstétrica", "quantity": 1, "week": 28},
            {"service_name": "Ecografía Obstétrica", "quantity": 1, "week": 32},
            {"service_name": "Ecografía Obstétrica", "quantity": 1, "week": 36},
            # Laboratorio
            {"service_name": "Hemograma completo", "quantity": 1, "week": 8},
            {"service_name": "Grupo sanguíneo y factor Rh", "quantity": 1, "week": 8},
            {"service_name": "Glucosa en ayunas", "quantity": 1, "week": 8},
            {"service_name": "Examen completo de orina", "quantity": 1, "week": 8},
            {"service_name": "RPR / VDRL", "quantity": 1, "week": 8},
            {"service_name": "VIH (prueba rápida/ELISA)", "quantity": 1, "week": 8},
        ],
    },
    {
        "name": "Paquete CPN B — Desde 15 semanas",
        "description": (
            "Control prenatal desde las 15 semanas para captación tardía. "
            "Incluye 5 consultas, ecografía morfológica, 2 ecografías de rutina "
            "y panel básico de laboratorio."
        ),
        "total_price": Decimal("950.00"),
        "valid_from_week": 15,
        "auto_schedule": True,
        "items": [
            # 5 consultas CPN
            {"service_name": "Control Prenatal", "quantity": 1, "week": 16},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 20, "desc": "CPN + Eco morfológica"},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 26},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 32},
            {"service_name": "Control Prenatal", "quantity": 1, "week": 36},
            # Ecografías
            {"service_name": "Ecografía Morfológica", "quantity": 1, "week": 20},
            {"service_name": "Ecografía Obstétrica", "quantity": 1, "week": 28},
            {"service_name": "Ecografía Obstétrica", "quantity": 1, "week": 34},
            # Laboratorio
            {"service_name": "Hemograma completo", "quantity": 1, "week": 16},
            {"service_name": "Glucosa en ayunas", "quantity": 1, "week": 16},
            {"service_name": "Examen completo de orina", "quantity": 1, "week": 16},
            {"service_name": "RPR / VDRL", "quantity": 1, "week": 16},
            {"service_name": "VIH (prueba rápida/ELISA)", "quantity": 1, "week": 16},
        ],
    },
]


async def seed_cpn_packages(clinic_id: UUID) -> None:
    """Crea los paquetes CPN si no existen."""

    async with async_session_factory() as db:
        for pkg_data in PACKAGES:
            # Verificar si ya existe
            result = await db.execute(
                select(ServicePackage).where(
                    ServicePackage.clinic_id == clinic_id,
                    ServicePackage.name == pkg_data["name"],
                )
            )
            if result.scalar_one_or_none():
                print(f"  SKIP: '{pkg_data['name']}' ya existe")
                continue

            # Crear paquete
            pkg = ServicePackage(
                clinic_id=clinic_id,
                name=pkg_data["name"],
                description=pkg_data["description"],
                total_price=pkg_data["total_price"],
                valid_from_week=pkg_data["valid_from_week"],
                auto_schedule=pkg_data["auto_schedule"],
                is_active=True,
            )
            db.add(pkg)
            await db.flush()

            # Crear ítems
            items_created = 0
            for item_data in pkg_data["items"]:
                # Buscar servicio por nombre
                svc_result = await db.execute(
                    select(Service).where(
                        Service.clinic_id == clinic_id,
                        Service.name == item_data["service_name"],
                    )
                )
                service = svc_result.scalar_one_or_none()
                if not service:
                    print(f"  WARN: Servicio '{item_data['service_name']}' no encontrado, omitiendo ítem")
                    continue

                item = PackageItem(
                    package_id=pkg.id,
                    service_id=service.id,
                    quantity=item_data.get("quantity", 1),
                    description_override=item_data.get("desc"),
                    gestational_week_target=item_data.get("week"),
                )
                db.add(item)
                items_created += 1

            await db.commit()
            print(f"  OK: '{pkg_data['name']}' creado con {items_created} ítems")

    print("Seed de paquetes CPN completado.")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/seed_cpn_packages.py <clinic_id>")
        print("  clinic_id: UUID de la clínica")
        print("")
        print("NOTA: Los servicios deben existir primero.")
        print("      Ejecutar primero: python scripts/seed_services.py <clinic_id>")
        sys.exit(1)

    try:
        clinic_id = UUID(sys.argv[1])
    except ValueError:
        print(f"ERROR: '{sys.argv[1]}' no es un UUID válido")
        sys.exit(1)

    asyncio.run(seed_cpn_packages(clinic_id))


if __name__ == "__main__":
    main()
