"""Tests unitaires du client HTTP CKAN (helpers/api_client.py)."""

import asyncio
import ipaddress
from unittest import mock

import httpx
import pytest

import helpers.url_guard as url_guard
from helpers.api_client import (
    DatagovAPIError,
    DatagovClient,
    DownloadTooLargeError,
    UnsafeDownloadURLError,
)

BASE_URL = "https://catalog.data.gov.tn/api/3"

_PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def resolution_dns_simulee(monkeypatch):
    """Elimine toute resolution DNS reelle des tests de telechargement."""
    resolution = {f"example{i}.org": _PUBLIC_IP for i in range(6)}
    resolution["example.org"] = _PUBLIC_IP
    resolution["cdn.example.net"] = _PUBLIC_IP
    resolution["data.gov.tn"] = _PUBLIC_IP

    def fake_resolver(host: str):
        return [ipaddress.ip_address(resolution.get(host, host))]

    monkeypatch.setattr(url_guard, "_default_resolver", fake_resolver)


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


def _mock_client(handler, **kwargs):
    """Client reel branche sur un transport httpx simule (streaming inclus)."""
    return DatagovClient(base_url=BASE_URL, transport=httpx.MockTransport(handler), **kwargs)


class _EndlessStream(httpx.AsyncByteStream):
    """Flux sans fin, pour verifier que la coupe intervient en cours de lecture."""

    def __init__(self, chunk_size: int = 512) -> None:
        self.chunk_size = chunk_size
        self.chunks = 0

    async def __aiter__(self):
        while True:
            self.chunks += 1
            yield b"x" * self.chunk_size


def test_download_renvoie_octets():
    def handler(request):
        return httpx.Response(200, content=b"Date,Miskar\n1,2\n")

    raw = _call(_mock_client(handler).download("https://example.org/file.csv", max_bytes=1024))

    assert raw == b"Date,Miskar\n1,2\n"


def test_download_erreur_reseau():
    def handler(request):
        raise httpx.ConnectError("connexion refusee")

    with pytest.raises(DatagovAPIError, match="Erreur reseau lors du telechargement"):
        _call(_mock_client(handler).download("https://example.org/file.csv", max_bytes=1024))


def test_download_http_non_200():
    def handler(request):
        return httpx.Response(500)

    with pytest.raises(DatagovAPIError, match="HTTP 500"):
        _call(_mock_client(handler).download("https://example.org/file.csv", max_bytes=1024))


def test_download_refuse_url_non_publique():
    def handler(request):  # pragma: no cover - jamais appele
        raise AssertionError("le garde-fou doit bloquer avant la requete")

    with pytest.raises(UnsafeDownloadURLError, match="adresse publique"):
        _call(
            _mock_client(handler).download(
                "http://169.254.169.254/latest/meta-data/", max_bytes=1024
            )
        )


def test_download_refuse_schema_non_autorise():
    def handler(request):  # pragma: no cover - jamais appele
        raise AssertionError("le garde-fou doit bloquer avant la requete")

    with pytest.raises(UnsafeDownloadURLError, match="Schema d'URL interdit"):
        _call(_mock_client(handler).download("file:///etc/passwd", max_bytes=1024))


def test_download_refuse_hote_hors_liste_blanche():
    def handler(request):  # pragma: no cover - jamais appele
        raise AssertionError("le garde-fou doit bloquer avant la requete")

    client = _mock_client(handler)
    with pytest.raises(UnsafeDownloadURLError, match="Hote non autorise"):
        _call(
            client.download(
                "https://example.org/file.csv",
                max_bytes=1024,
                allowed_hosts=["*.data.gov.tn"],
            )
        )


def test_download_coupe_des_content_length_trop_gros():
    def handler(request):
        return httpx.Response(200, headers={"content-length": "99999"}, content=b"x")

    with pytest.raises(DownloadTooLargeError, match="declares"):
        _call(_mock_client(handler).download("https://example.org/f.csv", max_bytes=1024))


def test_download_coupe_le_flux_meme_sans_content_length():
    """La limite doit s'appliquer pendant la lecture, pas apres coup."""
    stream = _EndlessStream()

    def handler(request):
        return httpx.Response(200, stream=stream)

    with pytest.raises(DownloadTooLargeError, match="octets recus"):
        _call(_mock_client(handler).download("https://example.org/f.csv", max_bytes=1024))

    assert stream.chunks <= 4


def test_download_suit_une_redirection_puis_revalide():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "example.org":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})
        return httpx.Response(200, content=b"ok")  # pragma: no cover

    with pytest.raises(UnsafeDownloadURLError, match="adresse publique"):
        _call(_mock_client(handler).download("https://example.org/f.csv", max_bytes=1024))

    assert seen == ["https://example.org/f.csv"]


def test_download_accepte_une_redirection_publique():
    def handler(request):
        if request.url.host == "example.org":
            return httpx.Response(302, headers={"location": "https://cdn.example.net/f.csv"})
        return httpx.Response(200, content=b"ok")

    raw = _call(_mock_client(handler).download("https://example.org/f.csv", max_bytes=1024))
    assert raw == b"ok"


def test_download_refuse_boucle_de_redirections():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.org/f.csv"})

    with pytest.raises(DatagovAPIError, match="Trop de redirections"):
        _call(_mock_client(handler).download("https://example.org/f.csv", max_bytes=1024))


def test_download_masque_les_identifiants_dans_les_erreurs():
    def handler(request):
        return httpx.Response(500)

    with pytest.raises(DatagovAPIError) as exc:
        _call(
            _mock_client(handler).download("https://user:secret@example.org/f.csv", max_bytes=1024)
        )

    assert "secret" not in str(exc.value)


def test_aclose_ferme_le_client(client, fake_async_client):
    _call(client.aclose())
    fake_async_client.aclose.assert_called_once()
