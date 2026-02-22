"""
Fixtures compartidas para Pytest.
Configura base de datos de test y clientes HTTP.
"""

import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.clinic import Clinic
from app.models.user import User, UserRole

settings = get_settings()

# ── Engine de test (SQLite async o PostgreSQL de test) ─
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Crea y destruye las tablas para cada test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provee una sesión de DB de test."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP de test que usa la DB de test."""

    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_clinic(db_session: AsyncSession) -> Clinic:
    """Crea una clínica de test."""
    clinic = Clinic(
        id=uuid4(),
        name="Clínica Test",
        ruc="20123456789",
    )
    db_session.add(clinic)
    await db_session.commit()
    await db_session.refresh(clinic)
    return clinic


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_clinic: Clinic) -> User:
    """Crea un usuario admin de test."""
    user = User(
        id=uuid4(),
        clinic_id=test_clinic.id,
        email="admin@test.com",
        hashed_password=hash_password("TestPass123"),
        role=UserRole.CLINIC_ADMIN,
        first_name="Admin",
        last_name="Test",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
