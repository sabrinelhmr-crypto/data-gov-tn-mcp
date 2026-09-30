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

mcp = FastMCP(
    APP_NAME,
    # Une erreur de validation doit etre signalee, pas corrigee au silence :
    # sans cela, page_size="10" est converti en 10 par le serveur.
    strict_input_validation=True,
    # En production, ne pas renvoyer aux clients le detail des exceptions
    # internes (chemins d'API, messages amont, stack traces).
    mask_error_details=settings.MCP_ENV == "prod",
)
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


def _origin_allowlist() -> list[str]:
    """
    Origines autorisees pour le transport HTTP.

    En production, une liste '*' est refusee au demarrage : sur un endpoint
    MCP sans authentification, elle autorise n'importe quelle page web a
    interroger le serveur au nom de l'utilisateur (CDC 6.1).
    """
    origins = settings.allowed_origins_list
    if settings.MCP_ENV == "prod" and "*" in origins:
        raise RuntimeError(
            "ALLOWED_ORIGINS contient '*' alors que MCP_ENV=prod. Restreignez "
            "la variable aux origines reelles (ex: https://mcp.data.gov.tn) "
            "avant de demarrer en production."
        )
    if not settings.CORS_ENABLED:
        return []
    return origins


def create_app():
    """
    Construit l'application ASGI.

    host_origin_protection=True est indispensable : sans lui, FastMCP installe
    les listes allowed_hosts/allowed_origins mais n'installe PAS le middleware
    de verification, qui reste le defaut a False. La protection active alors
    rejecte un Host inconnu (421) et une origine etrangere (403), ce qui bloque
    le DNS rebinding et les appels depuis une page web tierce (CDC 6.1).
    stateless_http supprime tout etat de session cote serveur.
    """
    return mcp.http_app(
        host_origin_protection=True,
        allowed_hosts=settings.allowed_hosts_list,
        allowed_origins=_origin_allowlist(),
        stateless_http=True,
    )


# App Starlette exposee (utilisee par les tests et le deploiement ASGI).
app = create_app()


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
    )
