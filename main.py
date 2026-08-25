# -*- coding: utf-8 -*-
"""
Point d'entree FastMCP + Uvicorn - serveur MCP data.gov.tn
"""

from datetime import datetime, timezone
from starlette.responses import JSONResponse

from fastmcp import FastMCP
from config import settings
from logging_config import setup_logging

# Initialise le logging structure JSON avant tout le reste
setup_logging()

# Heure de demarrage du serveur, utilisee par /health
START_TIME = datetime.now(timezone.utc)

# Instance principale du serveur MCP
mcp = FastMCP("data.gov.tn-mcp")


@mcp.custom_route("/health", methods=["GET"])
async def health_route(request):
    return JSONResponse({
        "status": "healthy",
        "uptime_since": START_TIME.isoformat(),
        "version": "1.0.0",
        "env": settings.MCP_ENV,
        "data_env": settings.DATAGOV_API_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
    )