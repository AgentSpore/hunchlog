"""Pytest fixtures: isolated temp DB + ASGI httpx client."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hunchlog.core import config, db
from hunchlog.main import app


@pytest.fixture
def temp_db(tmp_path, monkeypatch) -> str:
    """Point settings at a fresh per-test sqlite file."""
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(config.settings, "db_path", path)
    monkeypatch.setattr(db.settings, "db_path", path)
    return path


@pytest_asyncio.fixture
async def client(temp_db) -> AsyncIterator[AsyncClient]:
    """ASGI client over a schema-initialized, seeded app."""
    await db.init_db()
    await db.seed_predictions()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def empty_client(temp_db) -> AsyncIterator[AsyncClient]:
    """ASGI client over an initialized but UNSEEDED app."""
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
