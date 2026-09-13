
"""Enregistrement des outils MCP."""

from fastmcp import FastMCP

from tools.get_dataset_info import get_dataset_info
from tools.get_resource_info import get_resource_info
from tools.list_dataset_resources import list_dataset_resources
from tools.search_dataservices import search_dataservices
from tools.search_datasets import search_datasets


def register_tools(mcp: FastMCP) -> None:
    """Enregistre tous les outils MCP exposes par le serveur."""
    mcp.add_tool(search_datasets)
    mcp.add_tool(get_dataset_info)
    mcp.add_tool(search_dataservices)
    mcp.add_tool(list_dataset_resources)
    mcp.add_tool(get_resource_info)

# Enregistrement des outils MCP

from fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    """Enregistre les outils read-only auprès du serveur MCP."""

    @mcp.tool(name="search_datasets")
    async def search_datasets(query: str, max_results: int = 10) -> dict:
        """Recherche de jeux de données par mots-clés."""
        return {"query": query, "results": []}

    @mcp.tool(name="search_dataservices")
    async def search_dataservices(query: str, max_results: int = 10) -> dict:
        """Recherche de dataservices (APIs externes)."""
        return {"query": query, "results": []}

    @mcp.tool(name="get_dataset_info")
    async def get_dataset_info(dataset_id: str) -> dict:
        """Métadonnées détaillées d'un jeu de données."""
        return {"dataset_id": dataset_id}

    @mcp.tool(name="get_resource_info")
    async def get_resource_info(resource_id: str) -> dict:
        """Métadonnées détaillées d'une ressource."""
        return {"resource_id": resource_id}

