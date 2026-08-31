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
