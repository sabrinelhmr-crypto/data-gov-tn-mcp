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
