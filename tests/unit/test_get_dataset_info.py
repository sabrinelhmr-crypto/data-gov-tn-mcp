from unittest.mock import AsyncMock, patch

from tools.get_dataset_info import get_dataset_info


def _package(dataset_id: str = "id1") -> dict:
    return {
        "title": "Population Tunisie",
        "id": dataset_id,
        "notes": "Recensement de la population.",
        "organization": {"title": "Ministère"},
        "tags": [{"name": "population"}],
        "license_id": "other-open",
        "license_title": "Licence Ouverte",
        "metadata_created": "2020-01-01T00:00:00.000000",
        "metadata_modified": "2023-01-01T00:00:00.000000",
        "num_resources": 3,
        "resources": [],
        "extras": [{"key": "frequency", "value": "annuelle"}],
    }


def _show_response(result: dict) -> dict:
    return {"success": True, "result": result}


async def test_get_dataset_info_empty_id() -> None:
    assert await get_dataset_info("   ") == "Veuillez fournir un identifiant de dataset."


async def test_get_dataset_info_empty_query_skips_api() -> None:
    with patch("tools.get_dataset_info.datagov_client.get", AsyncMock()) as mock:
        await get_dataset_info("")
    mock.assert_not_awaited()


async def test_get_dataset_info_returns_formatted_metadata() -> None:
    mock = AsyncMock(return_value=_show_response(_package()))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1")
    assert "Population Tunisie" in result
    assert "Licence : Licence Ouverte" in result
    assert "Fr" in result
    assert "annuelle" in result
    assert "Nombre de ressources : 3" in result
    assert "Qualité des métadonnées : 100%" in result


async def test_get_dataset_info_uses_frequency_from_extras() -> None:
    pkg = _package()
    pkg["extras"] = {"freq": "mensuelle"}
    mock = AsyncMock(return_value=_show_response(pkg))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1")
    assert "mensuelle" in result
    assert "100%" in result


async def test_get_dataset_info_quality_reports_missing_fields() -> None:
    pkg = _package()
    del pkg["license_id"]
    del pkg["license_title"]
    mock = AsyncMock(return_value=_show_response(pkg))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1")
    assert "88%" in result
    assert "Champs manquants : licence" in result


async def test_get_dataset_info_not_found() -> None:
    mock = AsyncMock(
        return_value={
            "success": False,
            "error": {"__type": "Not Found", "message": "Not found"},
        }
    )
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("inconnu")
    assert "Not found" in result


async def test_get_dataset_info_api_error_returns_message() -> None:
    from helpers.api_client import DataGovError

    mock = AsyncMock(side_effect=DataGovError("boom"))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1")
    assert "boom" in result


async def test_get_dataset_info_english_labels() -> None:
    mock = AsyncMock(return_value=_show_response(_package()))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1", lang="en")
    assert "Organization : Ministère" in result
    assert "License : Licence Ouverte" in result
    assert "Number of resources : 3" in result


async def test_get_dataset_info_arabic_labels() -> None:
    mock = AsyncMock(return_value=_show_response(_package()))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1", lang="ar")
    assert "المنظمة" in result
    assert "الترخيص" in result
    assert "جودة البيانات الوصفية" in result


async def test_get_dataset_info_invalid_lang_falls_back_to_french() -> None:
    mock = AsyncMock(return_value=_show_response(_package()))
    with patch("tools.get_dataset_info.datagov_client.get", mock):
        result = await get_dataset_info("id1", lang="de")
    assert "Organisation" in result
