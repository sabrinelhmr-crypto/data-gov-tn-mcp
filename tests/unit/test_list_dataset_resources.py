from unittest.mock import AsyncMock, patch

from tools.list_dataset_resources import list_dataset_resources


def _resource(resource_id: str, name: str, format: str = "csv", size=2048) -> dict:
    return {
        "id": resource_id,
        "name": name,
        "format": format,
        "size": size,
        "resource_type": "file",
        "url": f"https://catalog.data.gov.tn/{resource_id}.csv",
        "last_modified": "2023-01-01T00:00:00.000000",
        "datastore_active": False,
    }


def _package_with_resources(count: int) -> dict:
    return {
        "title": "Population Tunisie",
        "id": "id1",
        "resources": [_resource(f"r{i}", f"Ressource {i}") for i in range(count)],
    }


def _show_response(result: dict) -> dict:
    return {"success": True, "result": result}


async def test_list_dataset_resources_empty_id() -> None:
    assert await list_dataset_resources("  ") == "Veuillez fournir un identifiant de dataset."


async def test_list_dataset_resources_returns_formatted_list() -> None:
    mock = AsyncMock(return_value=_show_response(_package_with_resources(2)))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1")
    assert "2 ressource(s) pour 'Population Tunisie'" in result
    assert "Ressource 1" in result
    assert "Format : CSV" in result
    assert "2.0 Ko" in result
    assert "Tabular API : Non" in result


async def test_list_dataset_resources_without_resources() -> None:
    mock = AsyncMock(return_value=_show_response({"title": "Vide", "resources": []}))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1")
    assert "Aucune ressource attachée" in result


async def test_list_dataset_resources_paginates() -> None:
    mock = AsyncMock(return_value=_show_response(_package_with_resources(25)))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1", page=2)
    assert "Page 2/2 (20 par page)" in result
    assert "21. Ressource 20" in result
    assert "25. Ressource 24" in result


async def test_list_dataset_resources_shows_tabular_api() -> None:
    pkg = _package_with_resources(1)
    pkg["resources"][0]["datastore_active"] = True
    mock = AsyncMock(return_value=_show_response(pkg))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1")
    assert "Tabular API : Oui" in result


async def test_list_dataset_resources_not_found() -> None:
    mock = AsyncMock(
        return_value={
            "success": False,
            "error": {"__type": "Not Found", "message": "Not found"},
        }
    )
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("inconnu")
    assert "Not found" in result
    assert "inconnu" in result


async def test_list_dataset_resources_api_error_returns_message() -> None:
    from helpers.api_client import DataGovError

    mock = AsyncMock(side_effect=DataGovError("boom"))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1")
    assert "boom" in result


async def test_list_dataset_resources_english_labels() -> None:
    mock = AsyncMock(return_value=_show_response(_package_with_resources(1)))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1", lang="en")
    assert "1 resource(s) for 'Population Tunisie'" in result
    assert "Format : CSV" in result
    assert "Size : 2.0 Ko" in result
    assert "Tabular API : No" in result


async def test_list_dataset_resources_arabic_labels() -> None:
    mock = AsyncMock(return_value=_show_response(_package_with_resources(1)))
    with patch("tools.list_dataset_resources.datagov_client.get", mock):
        result = await list_dataset_resources("id1", lang="ar")
    assert "التنسيق" in result
    assert "الحجم" in result
    assert "Tabular API : لا" in result
