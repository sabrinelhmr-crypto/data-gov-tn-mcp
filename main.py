"""
Point d'entree FastMCP + Uvicorn - serveur MCP data.gov.tn
"""

from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from config import settings
from helpers.api_client import DatagovAPIError, datagov_client
from logging_config import setup_logging
from tools import register_tools

setup_logging()

APP_NAME = "data.gov.tn-mcp"

try:
    VERSION = version("datagouv-mcp-tn")
except PackageNotFoundError:  # source directe (python main.py)
    VERSION = "dev"

START_TIME = datetime.now(UTC)

mcp = FastMCP(APP_NAME)
register_tools(mcp)


def _base_health() -> dict[str, Any]:
    """Dictionnaire commun aux endpoints /health et /health/ready."""
    now = datetime.now(UTC)
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": VERSION,
        "env": settings.MCP_ENV,
        "data_env": settings.DATAGOV_API_ENV,
        "uptime_since": START_TIME.isoformat(),
        "uptime_seconds": round((now - START_TIME).total_seconds(), 1),
        "timestamp": now.isoformat(),
    }


@mcp.custom_route("/health", methods=["GET"])
async def health_route(request):
    """Liveness: le processus tourne. Rapide, sans appel externe."""
    info = _base_health()
    tools = await mcp.list_tools()
    info["tools_count"] = len(tools)
    return JSONResponse(info)


@mcp.custom_route("/health/ready", methods=["GET"])
async def ready_route(request):
    """Readiness: le serveur peut atteindre l'API data.gov.tn."""
    info = _base_health()
    api_status: dict[str, Any] = {"reachable": False}

    started = datetime.now(UTC)
    try:
        data = await datagov_client.get("/action/status_show")
        latency_ms = round((datetime.now(UTC) - started).total_seconds() * 1000, 1)
        api_status.update(
            {
                "reachable": True,
                "latency_ms": latency_ms,
                "ckan_version": (data.get("result") or {}).get("version"),
            }
        )
        info["status"] = "healthy"
    except DatagovAPIError as exc:
        api_status["error"] = str(exc)
        info["status"] = "degraded"

    info["api"] = api_status
    return JSONResponse(info, status_code=200 if info["status"] == "healthy" else 503)


# App Starlette exposée (utilisée par les tests et le déploiement ASGI).
app = mcp.http_app()


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
    )
