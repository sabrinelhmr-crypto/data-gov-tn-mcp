"""Fixtures pytest partagees."""

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from helpers.api_client import DatagovAPIError

search_mod = importlib.import_module("tools.search_datasets")
dataset_mod = importlib.import_module("tools.get_dataset_info")
dataservice_mod = importlib.import_module("tools.search_dataservices")
resources_mod = importlib.import_module("tools.list_dataset_resources")
resource_mod = importlib.import_module("tools.get_resource_info")
query_mod = importlib.import_module("tools.query_resource_data")
download_mod = importlib.import_module("tools.download_and_parse_resource")
metrics_mod = importlib.import_module("tools.get_metrics")

Handler = Callable[[dict[str, Any] | None], Awaitable[dict[str, Any]]]


class FakeDatagovClient:
    """Client CKAN factice : le handler retourne la reponse du test."""

    def __init__(self) -> None:
        self.handler: Handler | None = None
        self.path_handler: (
            Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]] | None
        ) = None
        self.download_handler: Callable[[str], Awaitable[bytes]] | None = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.path_handler is not None:
            return await self.path_handler(path, params)
        if self.handler is None:
            raise DatagovAPIError("Aucun handler configure pour ce test.")
        return await self.handler(params)

    async def download(self, url: str) -> bytes:
        if self.download_handler is None:
            raise DatagovAPIError("Aucun download_handler configure pour ce test.")
        return await self.download_handler(url)


@pytest.fixture
def datagov(monkeypatch: pytest.MonkeyPatch) -> FakeDatagovClient:
    """Substitue le client API dans les modules outils par une instance factice."""
    fake = FakeDatagovClient()
    monkeypatch.setattr(search_mod, "datagov_client", fake)
    monkeypatch.setattr(dataset_mod, "datagov_client", fake)
    monkeypatch.setattr(dataservice_mod, "datagov_client", fake)
    monkeypatch.setattr(resources_mod, "datagov_client", fake)
    monkeypatch.setattr(resource_mod, "datagov_client", fake)
    monkeypatch.setattr(query_mod, "datagov_client", fake)
    monkeypatch.setattr(download_mod, "datagov_client", fake)
    monkeypatch.setattr(metrics_mod, "datagov_client", fake)
    return fake
