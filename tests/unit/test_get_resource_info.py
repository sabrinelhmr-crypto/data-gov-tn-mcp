from unittest.mock import AsyncMock, patch

from tools.get_resource_info import get_resource_info


def _resource() -> dict:
    return {
        "id": "res1",
        "name": "Population.csv",
        "package_id": "pkg1",
        "format": "CSV",
        "mimetype": "text/csv",
        "url": "https://catalog.data.gov.tn/res1.csv",
        "size": 5120,
        "resource_type": "file",
        "created": "2020-01-01T00:00:00.000000",
        "last_modified": "2023-01-01T00:00:00.000000",
        "datastore_active": True,
        "hash": "abc123",
    }


def _show_response(result: dict) -> dict:
    return {"success": True, "result": result}


def _package_show_response(title: str) -> dict:
    return {"success": True, "result": {"title": title}}


async def test_get_resource_info_empty_id() -> None:
    assert await get_resource_info(" ") == "Veuillez fournir un identifiant de ressource."


async def test_get_resource_info_returns_formatted_metadata() -> None:
    mock = AsyncMock(
        side_effect=[_show_response(_resource()), _package_show_response("Population")]
    )
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1")
    assert "Population.csv" in result
    assert "Format : CSV" in result
    assert "MIME type : text/csv" in result
    assert "5.0 Ko" in result
    assert "Dataset parent : pkg1" in result
    assert "Titre : Population" in result
    assert "Tabular API : Oui" in result
    assert "Checksum : abc123" in result


async def test_get_resource_info_without_hash_and_parent() -> None:
    res = _resource()
    res.pop("hash")
    res["package_id"] = ""
    res["size"] = None
    mock = AsyncMock(return_value=_show_response(res))
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1")
    assert "Checksum : Non renseigné" in result
    assert "Taille : Non renseignée" in result
    assert "Dataset parent : Non renseigné" in result


async def test_get_resource_info_parent_lookup_failure_keeps_id() -> None:
    mock = AsyncMock(
        side_effect=[
            _show_response(_resource()),
            {"success": False, "error": {"message": "Not found"}},
        ]
    )
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1")
    assert "Dataset parent : pkg1" in result
    assert "Titre :" not in result


async def test_get_resource_info_not_found() -> None:
    mock = AsyncMock(
        return_value={
            "success": False,
            "error": {"__type": "Not Found", "message": "Not found"},
        }
    )
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("inconnu")
    assert "Not found" in result


async def test_get_resource_info_api_error_returns_message() -> None:
    from helpers.api_client import DataGovError

    mock = AsyncMock(side_effect=DataGovError("boom"))
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1")
    assert "boom" in result


async def test_get_resource_info_english_labels() -> None:
    mock = AsyncMock(
        side_effect=[_show_response(_resource()), _package_show_response("Population")]
    )
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1", lang="en")
    assert "Format : CSV" in result
    assert "MIME type : text/csv" in result
    assert "Parent dataset : pkg1" in result
    assert "Title : Population" in result
    assert "Tabular API availability : Yes" in result
    assert "Checksum : abc123" in result


async def test_get_resource_info_arabic_labels() -> None:
    mock = AsyncMock(
        side_effect=[_show_response(_resource()), _package_show_response("Population")]
    )
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1", lang="ar")
    assert "مجموعة البيانات الأصلية" in result
    assert "المجموع الاختباري" in result
