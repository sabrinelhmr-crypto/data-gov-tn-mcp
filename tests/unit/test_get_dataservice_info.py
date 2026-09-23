from unittest.mock import AsyncMock, patch

from tools.get_dataservice_info import get_dataservice_info


def _service() -> dict:
    return {
        "title": "API Cartographie",
        "id": "ds1",
        "type": "dataservice",
        "url": "https://api.data.gov.tn/maps",
        "notes": "Données cartographiques de la Tunisie.",
        "resources": [
            {
                "id": "r1",
                "name": "Endpoint principal",
                "url": "https://api.data.gov.tn/maps/geojson",
                "format": "json",
                "resource_type": "api",
            },
            {
                "id": "r2",
                "name": "Documentation",
                "url": "https://api.data.gov.tn/maps/docs",
                "format": "documentation",
                "resource_type": "documentation",
            },
        ],
    }


def _show_response(result: dict) -> dict:
    return {"success": True, "result": result}


async def test_get_dataservice_info_empty_id() -> None:
    assert await get_dataservice_info("  ") == "Veuillez fournir un identifiant de dataservice."


async def test_get_dataservice_info_returns_formatted_metadata() -> None:
    mock = AsyncMock(return_value=_show_response(_service()))
    with patch("tools.get_dataservice_info.datagov_client.get", mock):
        result = await get_dataservice_info("ds1")
    assert "API Cartographie" in result
    assert "URL de base : https://api.data.gov.tn/maps" in result
    assert "Endpoint principal : https://api.data.gov.tn/maps/geojson" in result
    assert "Format de réponse : JSON" in result
    assert "Documentation : https://api.data.gov.tn/maps/docs" in result


async def test_get_dataservice_info_without_resources() -> None:
    service = {
        "title": "API Simple",
        "id": "ds2",
        "url": "https://api.data.gov.tn/x",
        "resources": [],
        "notes": "",
    }
    mock = AsyncMock(return_value=_show_response(service))
    with patch("tools.get_dataservice_info.datagov_client.get", mock):
        result = await get_dataservice_info("ds2")
    assert "URL de base : https://api.data.gov.tn/x" in result
    assert "Endpoint principal : Non renseigné" in result
    assert "Documentation : Non renseignée" in result


async def test_get_dataservice_info_not_found() -> None:
    mock = AsyncMock(
        return_value={
            "success": False,
            "error": {"__type": "Not Found", "message": "Not found"},
        }
    )
    with patch("tools.get_dataservice_info.datagov_client.get", mock):
        result = await get_dataservice_info("inconnu")
    assert "Not found" in result


async def test_get_dataservice_info_api_error_returns_message() -> None:
    from helpers.api_client import DataGovError

    mock = AsyncMock(side_effect=DataGovError("boom"))
    with patch("tools.get_dataservice_info.datagov_client.get", mock):
        result = await get_dataservice_info("ds1")
    assert "boom" in result


async def test_get_dataservice_info_english_labels() -> None:
    mock = AsyncMock(return_value=_show_response(_service()))
    with patch("tools.get_dataservice_info.datagov_client.get", mock):
        result = await get_dataservice_info("ds1", lang="en")
    assert "Base URL : https://api.data.gov.tn/maps" in result
    assert "Main endpoint : https://api.data.gov.tn/maps/geojson" in result
    assert "Response format : JSON" in result
    assert "Documentation : https://api.data.gov.tn/maps/docs" in result


async def test_get_dataservice_info_arabic_labels() -> None:
    mock = AsyncMock(return_value=_show_response(_service()))
    with patch("tools.get_dataservice_info.datagov_client.get", mock):
        result = await get_dataservice_info("ds1", lang="ar")
    assert "الرابط الأساسي" in result
    assert "التوثيق" in result
