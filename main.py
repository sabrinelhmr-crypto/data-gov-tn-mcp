"""
Point d'entree FastMCP + Uvicorn - serveur MCP data.gov.tn
"""

from datetime import UTC, datetime

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from config import settings
from logging_config import setup_logging
from tools import register_tools

setup_logging()

START_TIME = datetime.now(UTC)
mcp = FastMCP("data.gov.tn-mcp")
register_tools(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health_route(request):
    return JSONResponse(
        {
            "status": "healthy",
            "uptime_since": START_TIME.isoformat(),
            "version": "1.0.0",
            "env": settings.MCP_ENV,
            "data_env": settings.DATAGOV_API_ENV,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
    )
