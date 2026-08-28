"""Tests unitaires du client HTTP CKAN (helpers/api_client.py)."""

import asyncio
from unittest import mock

import httpx
import pytest

from helpers.api_client import DatagovAPIError, DatagovClient

BASE_URL = "https://catalog.data.gov.tn/api/3"


@pytest.fixture
def async_client_cls(monkeypatch):
    """Mocke httpx.AsyncClient (le constructeur) dans le module api_client."""
    import helpers.api_client as api_mod

    cls = mock.MagicMock()
    monkeypatch.setattr(api_mod.httpx, "AsyncClient", cls)
    return cls


@pytest.fixture
def fake_async_client(async_client_cls):
    """Instance AsyncClient factice avec get/aclose asynchrones."""
    client = mock.MagicMock()
    client.get = mock.AsyncMock()
    client.aclose = mock.AsyncMock()
    async_client_cls.return_value = client
    return client


@pytest.fixture
def client(fake_async_client):
    return DatagovClient(base_url=BASE_URL, timeout=15)


def _call(coroutine):
    return asyncio.run(coroutine)


def test_init_ecrase_le_slash_final():
    c = DatagovClient(base_url="https://catalog.data.gov.tn/api/3/")
    assert c._base_url == "https://catalog.data.gov.tn/api/3"


def test_init_envoie_api_key(async_client_cls):
    DatagovClient(base_url=BASE_URL, api_key="secret-key")
    kwargs = async_client_cls.call_args.kwargs
    assert kwargs["headers"] == {"Authorization": "secret-key"}


def test_init_sans_api_key(async_client_cls):
    DatagovClient(base_url=BASE_URL)
    assert async_client_cls.call_args.kwargs["headers"] == {}


def test_get_renvoie_payload_json(client, fake_async_client):
    fake_async_client.get.return_value = httpx.Response(
        200, json={"success": True, "result": {"count": 3}}
    )

    data = _call(client.get("/action/package_search", {"q": "eau"}))

    assert data["result"]["count"] == 3
    fake_async_client.get.assert_called_once_with("/action/package_search", params={"q": "eau"})


def test_get_erreur_reseau(client, fake_async_client):
    fake_async_client.get.side_effect = httpx.ConnectError("connexion refusee")

    with pytest.raises(DatagovAPIError, match="Erreur reseau"):
        _call(client.get("/action/package_search"))


def test_get_http_non_200(client, fake_async_client):
    fake_async_client.get.return_value = httpx.Response(404)

    with pytest.raises(DatagovAPIError, match="HTTP 404"):
        _call(client.get("/action/package_show", {"id": "x"}))


def test_get_reponse_non_json(client, fake_async_client):
    fake_async_client.get.return_value = httpx.Response(200, text="<html>oups</html>")

    with pytest.raises(DatagovAPIError, match="non-JSON"):
        _call(client.get("/action/package_search"))


def test_get_success_false(client, fake_async_client):
    fake_async_client.get.return_value = httpx.Response(
        200, json={"success": False, "error": {"message": "Not found"}}
    )

    with pytest.raises(DatagovAPIError, match="Not found"):
        _call(client.get("/action/package_show", {"id": "abc"}))


def test_get_success_false_sans_message(client, fake_async_client):
    fake_async_client.get.return_value = httpx.Response(200, json={"success": False})

    with pytest.raises(DatagovAPIError, match="Erreur CKAN inconnue"):
        _call(client.get("/action/package_search"))


def test_aclose_ferme_le_client(client, fake_async_client):
    _call(client.aclose())
    fake_async_client.aclose.assert_called_once()
