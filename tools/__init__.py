"""Enregistrement des outils MCP."""

from fastmcp import FastMCP

from tools.download_and_parse_resource import download_and_parse_resource
from tools.get_dataservice_info import get_dataservice_info
from tools.get_dataservice_openapi_spec import get_dataservice_openapi_spec
from tools.get_dataset_info import get_dataset_info
from tools.get_metrics import get_metrics
from tools.get_resource_info import get_resource_info
from tools.list_dataset_resources import list_dataset_resources
from tools.query_resource_data import query_resource_data
from tools.search_dataservices import search_dataservices
from tools.search_datasets import search_datasets


def register_tools(mcp: FastMCP) -> None:
    """Enregistre les 9 outils read-only du serveur (CDC section 4.1).

    A1, A2 recherche  B1-B5 inspection  C1-C3 analyse
    """
    # Famille A - Recherche et decouverte
    mcp.add_tool(search_datasets)
    mcp.add_tool(search_dataservices)
    # Famille B - Inspection et metadonnees
    mcp.add_tool(get_dataset_info)
    mcp.add_tool(list_dataset_resources)
    mcp.add_tool(get_resource_info)
    mcp.add_tool(get_dataservice_info)
    mcp.add_tool(get_dataservice_openapi_spec)
    # Famille C - Analyse de donnees
    mcp.add_tool(query_resource_data)
    mcp.add_tool(download_and_parse_resource)
    mcp.add_tool(get_metrics)
