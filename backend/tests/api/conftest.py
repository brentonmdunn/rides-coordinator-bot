"""Shared fixtures for API integration tests.

These tests build a fresh FastAPI app per fixture so we never actually start
the Discord bot or open a real database connection. Individual routers are
mounted directly and their dependencies are mocked at the module level.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure local mode so Cloudflare auth is bypassed and no real env required.
os.environ.setdefault("APP_ENV", "local")


@pytest.fixture
def app_factory() -> Iterator[callable]:
    """
    Returns a callable that builds a FastAPI app with the given routers.

    Usage:
        app = app_factory(router_a, router_b)
        client = TestClient(app)
    """

    def _factory(*routers) -> FastAPI:
        app = FastAPI()
        for router in routers:
            app.include_router(router)
        return app

    yield _factory


@pytest.fixture
def fake_bot() -> MagicMock:
    """A bot stub with the minimal surface required by API routes."""
    bot = MagicMock()
    bot.is_ready.return_value = True
    return bot


@pytest.fixture
def client_factory():
    """Factory that returns TestClient instances for ad-hoc apps."""

    def _factory(app: FastAPI) -> TestClient:
        return TestClient(app)

    return _factory
