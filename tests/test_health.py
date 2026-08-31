"""Tests unitaires du health check (/health et /health/ready)."""

import importlib
from datetime import datetime

import httpx
import pytest

from helpers.api_client import DatagovAPIError

main_mod = importlib.import_module("main")


@pytest.fixture(scope="module")
async def asgi_client():
    """Client ASGI contre l'app Starlette FastMCP."""
    transport = httpx.ASGITransport(app=main_mod.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client


async def test_health_liveness(monkeypatch, asgi_client):
    async def boom(*args, **kwargs):
        raise DatagovAPIError("ne doit pas etre appele")

    monkeypatch.setattr(main_mod, "datagov_client", type("X", (), {"get": boom})())

    response = await asgi_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "data.gov.tn-mcp"
    assert body["version"]
    assert body["tools_count"] == 4
    assert body["uptime_since"]
    assert body["uptime_seconds"] >= 0


async def test_health_liveness_no_api_call(monkeypatch, asgi_client):
    call_count = 0

    async def track_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise DatagovAPIError("ne doit pas etre appele")

    monkeypatch.setattr(
        main_mod, "datagov_client", type("X", (), {"get": track_call})()
    )

    await asgi_client.get("/health")
    assert call_count == 0


async def test_health_liveness_uptime_increases(monkeypatch, asgi_client):
    async def noop(*args, **kwargs):
        raise DatagovAPIError("noop")

    monkeypatch.setattr(main_mod, "datagov_client", type("X", (), {"get": noop})())

    resp1 = await asgi_client.get("/health")
    resp2 = await asgi_client.get("/health")

    t1 = resp1.json()["uptime_seconds"]
    t2 = resp2.json()["uptime_seconds"]
    assert t2 >= t1


async def test_health_liveness_base_fields(monkeypatch, asgi_client):
    async def noop(*args, **kwargs):
        raise DatagovAPIError("noop")

    monkeypatch.setattr(main_mod, "datagov_client", type("X", (), {"get": noop})())

    response = await asgi_client.get("/health")
    body = response.json()

    assert "env" in body
    assert "data_env" in body
    assert "timestamp" in body
    ts = datetime.fromisoformat(body["timestamp"])
    assert ts.tzinfo is not None


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


async def test_health_ready_only_catches_datagov_error(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            raise RuntimeError("unexpected")

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    with pytest.raises(RuntimeError):
        await asgi_client.get("/health/ready")


async def test_health_ready_latency_positive(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            return {"success": True, "result": {"version": "2.11.0"}}

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    response = await asgi_client.get("/health/ready")
    body = response.json()
    assert isinstance(body["api"]["latency_ms"], (int, float))
    assert body["api"]["latency_ms"] >= 0


async def test_health_ready_base_fields(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            return {"success": True, "result": {"version": "2.11.0"}}

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    response = await asgi_client.get("/health/ready")
    body = response.json()

    assert "service" in body
    assert body["service"] == "data.gov.tn-mcp"
    assert "version" in body
    assert "uptime_since" in body
    assert "uptime_seconds" in body
    assert "api" in body
    assert isinstance(body["api"], dict)


async def test_health_ready_api_missing_version(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            return {"success": True, "result": {}}

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    response = await asgi_client.get("/health/ready")
    body = response.json()
    assert body["status"] == "healthy"
    assert body["api"]["reachable"] is True
    assert body["api"]["ckan_version"] is None


async def test_health_ready_api_empty_result(monkeypatch, asgi_client):
    class FakeClient:
        async def get(self, path, params=None):
            return {"success": True, "result": None}

    monkeypatch.setattr(main_mod, "datagov_client", FakeClient())

    response = await asgi_client.get("/health/ready")
    body = response.json()
    assert body["status"] == "healthy"
    assert body["api"]["reachable"] is True
    assert body["api"]["ckan_version"] is None


async def test_health_tools_count_matches_registered(monkeypatch, asgi_client):
    async def noop(*args, **kwargs):
        raise DatagovAPIError("noop")

    monkeypatch.setattr(main_mod, "datagov_client", type("X", (), {"get": noop})())

    response = await asgi_client.get("/health")
    body = response.json()

    tools = await main_mod.mcp.list_tools()
    assert body["tools_count"] == len(tools)
