"""
Alembic env.py — configurado para SQLAlchemy async + auto-detección de modelos.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database import Base

# Importar TODOS los modelos para que Alembic los detecte
from app.models import (  # noqa: F401
    Clinic, User, Patient, AuditLog,
    Appointment, DoctorSchedule,
    MedicalRecord, DentalChart, PrenatalVisit, OphthalmicExam,
    Invoice, InvoiceItem,
    SyncQueue, SyncDeviceMapping,
    Supplier, InventoryCategory, InventoryItem, StockMovement,
    Service,
)
from app.models.cash_register import CashSession, CashMovement  # noqa: F401
from app.models.staff_schedule_override import StaffScheduleOverride  # noqa: F401

settings = get_settings()

# ── Alembic Config ───────────────────────────────────
config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecutar migraciones en modo 'offline' (genera SQL sin conectar)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Ejecutar migraciones en modo 'online' con engine async."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Wrapper para ejecutar migraciones async."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
