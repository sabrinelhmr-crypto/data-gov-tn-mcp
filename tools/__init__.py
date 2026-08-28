"""Enregistrement des outils MCP."""

from fastmcp import FastMCP

from tools.get_dataset_info import get_dataset_info
from tools.search_datasets import search_datasets


def register_tools(mcp: FastMCP) -> None:
    """Enregistre tous les outils MCP exposes par le serveur."""
    mcp.add_tool(search_datasets)
    mcp.add_tool(get_dataset_info)
