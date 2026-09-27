from unittest.mock import AsyncMock, patch

import httpx

from tools.get_dataservice_openapi_spec import get_dataservice_openapi_spec


class _FakeStream:
    def __init__(self, content: bytes = b"", error: bool = False) -> None:
        self._content = content
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self._error:
            raise httpx.HTTPError("boom")

    async def aiter_bytes(self):
        yield self._content


class _FakeClient:
    def __init__(self, *args, content: bytes = b"", error: bool = False, **kwargs):
        self._content = content
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    def stream(self, method: str, url: str, **kwargs):
        return _FakeStream(self._content, error=self._error)


def _show_response(result: dict) -> dict:
    return {"success": True, "result": result}


def _service(url: str | None = "https://api.data.gov.tn/x", resources: list | None = None) -> dict:
    return {
        "title": "API Test",
        "id": "ds1",
        "url": url,
        "resources": resources or [],
        "extras": [],
    }


async def test_get_dataservice_openapi_spec_empty_id() -> None:
    assert (
        await get_dataservice_openapi_spec("  ")
        == "Veuillez fournir un identifiant de dataservice."
    )


async def test_get_dataservice_openapi_spec_returns_json() -> None:
    service = _service(
        resources=[{"format": "openapi", "url": "https://api.data.gov.tn/spec.json"}]
    )
    spec = b'{"openapi": "3.0.0", "info": {"title": "API Test"}}'
    mock = AsyncMock(return_value=_show_response(service))
    with (
        patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock),
        patch(
            "tools.get_dataservice_openapi_spec.httpx.AsyncClient",
            return_value=_FakeClient(content=spec),
        ),
    ):
        result = await get_dataservice_openapi_spec("ds1")
    assert "Spécification OpenAPI de 'API Test'" in result
    assert "ressource du dataservice" in result
    assert '"openapi": "3.0.0"' in result


async def test_get_dataservice_openapi_spec_yaml_passthrough() -> None:
    service = _service(resources=[{"format": "openapi", "url": "https://x/spec.yaml"}])
    mock = AsyncMock(return_value=_show_response(service))
    with (
        patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock),
        patch(
            "tools.get_dataservice_openapi_spec.httpx.AsyncClient",
            return_value=_FakeClient(content=b"openapi: 3.0.0\n"),
        ),
    ):
        result = await get_dataservice_openapi_spec("ds1")
    assert "openapi: 3.0.0" in result


async def test_get_dataservice_openapi_spec_derived_from_base_url() -> None:
    service = _service(url="https://api.data.gov.tn/maps")
    spec = b'{"openapi": "3.0.1"}'
    mock = AsyncMock(return_value=_show_response(service))
    with (
        patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock),
        patch(
            "tools.get_dataservice_openapi_spec.httpx.AsyncClient",
            return_value=_FakeClient(content=spec),
        ),
    ):
        result = await get_dataservice_openapi_spec("ds1")
    assert "dérivée de l'URL de base" in result


async def test_get_dataservice_openapi_spec_not_found() -> None:
    service = _service(url=None)
    mock = AsyncMock(return_value=_show_response(service))
    with patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock):
        result = await get_dataservice_openapi_spec("ds1")
    assert "Aucune spécification OpenAPI trouvée" in result


async def test_get_dataservice_openapi_spec_http_error() -> None:
    service = _service(resources=[{"format": "openapi", "url": "https://x/spec.json"}])
    mock = AsyncMock(return_value=_show_response(service))
    with (
        patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock),
        patch(
            "tools.get_dataservice_openapi_spec.httpx.AsyncClient",
            return_value=_FakeClient(error=True),
        ),
    ):
        result = await get_dataservice_openapi_spec("ds1")
    assert "Impossible de récupérer la spécification" in result


async def test_get_dataservice_openapi_spec_api_error() -> None:
    mock = AsyncMock(return_value={"success": False, "error": {"message": "Not found"}})
    with patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock):
        result = await get_dataservice_openapi_spec("inconnu")
    assert "Not found" in result


async def test_get_dataservice_openapi_spec_transport_error() -> None:
    from helpers.api_client import DataGovError

    mock = AsyncMock(side_effect=DataGovError("boom"))
    with patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock):
        result = await get_dataservice_openapi_spec("ds1")
    assert "boom" in result


async def test_get_dataservice_openapi_spec_english_header() -> None:
    service = _service(resources=[{"format": "openapi", "url": "https://x/spec.json"}])
    spec = b'{"openapi": "3.0.0"}'
    mock = AsyncMock(return_value=_show_response(service))
    with (
        patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock),
        patch(
            "tools.get_dataservice_openapi_spec.httpx.AsyncClient",
            return_value=_FakeClient(content=spec),
        ),
    ):
        result = await get_dataservice_openapi_spec("ds1", lang="en")
    assert "OpenAPI specification of 'API Test'" in result
    assert "source: data service resource" in result


async def test_get_dataservice_openapi_spec_arabic_error() -> None:
    service = _service(resources=[{"format": "openapi", "url": "https://x/spec.json"}])
    mock = AsyncMock(return_value=_show_response(service))
    with (
        patch("tools.get_dataservice_openapi_spec.datagov_client.get", mock),
        patch(
            "tools.get_dataservice_openapi_spec.httpx.AsyncClient",
            return_value=_FakeClient(error=True),
        ),
    ):
        result = await get_dataservice_openapi_spec("ds1", lang="ar")
    assert "تعذّر استرجاع المواصفة" in result
