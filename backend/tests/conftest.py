"""Shared test fixtures."""

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
DATA_DIR = pathlib.Path(__file__).parent.parent / "data"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch):
    """Keep the suite hermetic — tests must never depend on a local Redis.

    ``RateLimitMiddleware`` fails open without Redis, but if a developer does
    have Redis running a shared counter could leak between tests, so the
    limiter is switched off globally here.
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")


@pytest.fixture
def settings_no_imd():
    """Settings without an IMD key — IMD provider must fail closed."""
    from app.core.config import Settings

    return Settings(imd_api_key="", imd_enabled=True)


@pytest.fixture
def client_no_imd(settings_no_imd):
    """App where IMD is unconfigured; Open-Meteo is the only real provider."""
    from app.main import create_app

    return TestClient(create_app(settings_no_imd))