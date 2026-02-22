"""
Script de data migration: calcula org_dni_hash para pacientes existentes.

Debe ejecutarse DESPUÉS de la migración Alembic g7h8i9j0k1l2.
Descifra el DNI con Fernet y calcula SHA-256(org_id:dni) para cada paciente
que pertenezca a una organización.

Uso:
    python scripts/migrate_org_dni_hash.py
"""

import asyncio
import hashlib
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.core.security import decrypt_pii
from app.models.patient import Patient


async def migrate_org_dni_hash() -> None:
    """Calcula y setea org_dni_hash para todos los pacientes con organization_id."""
    async with async_session_factory() as db:
        # Desactivar RLS temporalmente para acceder a todos los pacientes
        await db.execute(text("SET LOCAL row_security = off"))

        # Obtener pacientes con organization_id pero sin org_dni_hash
        result = await db.execute(
            select(Patient).where(
                Patient.organization_id.isnot(None),
                Patient.org_dni_hash.is_(None),
            )
        )
        patients = result.scalars().all()

        print(f"Procesando {len(patients)} pacientes...")

        updated = 0
        duplicates = 0
        seen_hashes: dict[str, str] = {}  # org_dni_hash -> patient.id

        for patient in patients:
            try:
                # Descifrar DNI
                dni_plain = decrypt_pii(patient.dni)
                if not dni_plain:
                    print(f"  SKIP: Patient {patient.id} tiene DNI vacío")
                    continue

                # Calcular org_dni_hash
                raw = f"{patient.organization_id}:{dni_plain}"
                org_hash = hashlib.sha256(raw.encode()).hexdigest()

                if org_hash in seen_hashes:
                    # Duplicado detectado dentro de la misma org
                    duplicates += 1
                    print(
                        f"  DUPLICADO: Patient {patient.id} tiene mismo DNI "
                        f"que Patient {seen_hashes[org_hash]} en la misma org"
                    )
                    # No seteamos el hash (se debe resolver manualmente o con merge)
                    continue

                patient.org_dni_hash = org_hash
                seen_hashes[org_hash] = str(patient.id)
                updated += 1

            except Exception as e:
                print(f"  ERROR: Patient {patient.id}: {e}")

        await db.commit()
        print(f"\nResultados:")
        print(f"  Actualizados: {updated}")
        print(f"  Duplicados detectados: {duplicates}")
        print(f"  Total procesados: {len(patients)}")

        if duplicates > 0:
            print(
                "\n⚠ Se detectaron pacientes duplicados en la misma organización."
                "\n  Deben resolverse manualmente (merge de registros) antes de"
                "\n  que la dedup cross-sede funcione correctamente."
            )


if __name__ == "__main__":
    asyncio.run(migrate_org_dni_hash())
