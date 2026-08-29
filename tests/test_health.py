"""Tests unitaires du health check (/health et /health/ready)."""

import importlib

import httpx
import pytest

from helpers.api_client import DatagovAPIError

main_mod = importlib.import_module("main")


@pytest.fixture(scope="module")
async def asgi_client():
    """Client ASGI contre l'app Starlette FastMCP."""
    transport = httpx.ASGITransport(app=main_mod.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_health_liveness(monkeypatch, asgi_client):
    # Pas d'appel externe attendu sur /health : on casse le client API.
    async def boom(*args, **kwargs):
        raise DatagovAPIError("ne doit pas etre appele")

    monkeypatch.setattr(main_mod, "datagov_client", type("X", (), {"get": boom})())

    response = await asgi_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "data.gov.tn-mcp"
    assert body["version"]
    assert body["tools_count"] == 1
    assert body["uptime_since"]
    assert body["uptime_seconds"] >= 0


async def test_health_ready_api_ok(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            assert path == "/action/status_show"
            return {"success": True, "result": {"version": "2.11.0"}}

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    response = await asgi_client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["api"]["reachable"] is True
    assert body["api"]["latency_ms"] >= 0
    assert body["api"]["ckan_version"] == "2.11.0"


async def test_health_ready_api_down(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            raise DatagovAPIError("API down")

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    response = await asgi_client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["api"]["reachable"] is False
    assert "API down" in body["api"]["error"]
