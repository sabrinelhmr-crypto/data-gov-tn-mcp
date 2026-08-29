"""Fixtures pytest partagees."""

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from helpers.api_client import DatagovAPIError

dataset_mod = importlib.import_module("tools.get_dataset_info")

Handler = Callable[[dict[str, Any] | None], Awaitable[dict[str, Any]]]


class FakeDatagovClient:
    """Client CKAN factice : le handler retourne la reponse du test."""

    def __init__(self) -> None:
        self.handler: Handler | None = None

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.handler is None:
            raise DatagovAPIError("Aucun handler configure pour ce test.")
        return await self.handler(params)


@pytest.fixture
def datagov(monkeypatch: pytest.MonkeyPatch) -> FakeDatagovClient:
    """Substitue le client API dans les modules outils par une instance factice."""
    fake = FakeDatagovClient()
    monkeypatch.setattr(dataset_mod, "datagov_client", fake)
    return fake
