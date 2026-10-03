"""Tests unitaires pour l'outil list_dataset_resources."""

from unittest.mock import AsyncMock, patch

from tools.list_dataset_resources import _human_size, list_dataset_resources


def _dataset(resources=None):
    return {
        "id": "abc-123",
        "name": "titre-test",
        "title": "Titre test",
        "organization": {"name": "org-test", "title": "Org Test"},
        "resources": resources if resources is not None else [],
    }


def _resource(**overrides):
    values = {
        "id": "res-1",
        "name": "Donnees 2024",
        "format": "CSV",
        "url": "https://example.org/file.csv",
        "resource_type": "file",
        "description": "Fichier principal",
        "datastore_active": True,
        "downloads_count": 42,
        "size": 2048,
        "created": "2023-01-01T00:00:00",
        "last_modified": "2024-02-01T00:00:00",
    }
    values.update(overrides)
    return values


def _payload(dataset):
    return {"success": True, "result": dataset}


async def test_liste_formule_package_show(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload(_dataset([_resource()]))

    datagov.handler = handler

    await list_dataset_resources("abc-123")
    assert captured == {"id": "abc-123"}


async def test_liste_affichage_dataset(datagov):
    async def handler(params):
        return _payload(_dataset([_resource()]))

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "1 ressource(s) pour 'Titre test' :" in out
    assert "Page 1/1 (20 par page)" in out
    # Le header ne reprend plus slug ni organisation : ils sont exposes par
    # get_dataset_info (B1).
    assert "Slug : titre-test" not in out
    assert "Organisation : Org Test" not in out


async def test_liste_affichage_ressource(datagov):
    async def handler(params):
        return _payload(_dataset([_resource()]))

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "1. Donnees 2024" in out
    assert "   ID : res-1" in out
    assert "   URL : https://example.org/file.csv" in out
    assert "   Type : file" in out
    assert "   Tabular API : Oui" in out
    assert "   Taille : 2.0 Ko" in out
    assert "   Dernière modification : 2024-02-01T00:00:00" in out
    # Le nombre de telechargements et la description ne sont pas exposes.
    assert "Téléchargements :" not in out
    assert "Description :" not in out


async def test_liste_plusieurs_ressources(datagov):
    async def handler(params):
        return _payload(
            _dataset(
                [
                    _resource(id="res-1", name="Donnees", format="CSV"),
                    _resource(
                        id="res-2",
                        name="Documentation",
                        format="PDF",
                        datastore_active=False,
                        downloads_count=None,
                        size=None,
                        last_modified=None,
                        created="2023-01-01T00:00:00",
                    ),
                ]
            )
        )

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "2 ressource(s) pour 'Titre test' :" in out
    assert "1. Donnees" in out
    assert "   Format : CSV" in out
    assert "2. Documentation" in out
    assert "   Format : PDF" in out
    assert "   Tabular API : Non" in out
    assert "   Taille : Non renseignée" in out
    assert "   Dernière modification : Non renseignée" in out


async def test_liste_sans_ressource(datagov):
    async def handler(params):
        return _payload(_dataset([]))

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "Aucune ressource attachée à ce dataset." in out


async def test_liste_dataset_introuvable(datagov):
    from helpers.api_client import DatagovAPIError

    async def handler(params):
        raise DatagovAPIError("Not found: abc")

    datagov.handler = handler

    out = await list_dataset_resources("abc-introuvable")
    assert "Not found: abc" in out


async def test_liste_requete_vide(datagov):
    out = await list_dataset_resources("   ")
    assert "Veuillez fournir un identifiant" in out


async def test_ressource_minimale(datagov):
    async def handler(params):
        return _payload(
            _dataset(
                [
                    {
                        "id": "res-min",
                        "name": "",
                        "format": "",
                        "url": "",
                        "datastore_active": False,
                    }
                ]
            )
        )

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "1. Ressource 1" in out
    assert "   Format : INCONNU" in out
    assert "   Type : file" in out
    assert "   Tabular API : Non" in out


def test_human_size():
    assert _human_size(500, "fr") == "500 o"
    assert _human_size(2048, "fr") == "2.0 Ko"
    assert _human_size(5 * 1024 * 1024, "fr") == "5.0 Mo"
    assert _human_size(3 * 1024 * 1024 * 1024, "fr") == "3.0 Go"
    assert _human_size(None, "fr") == "Non renseignée"
    assert _human_size("xyz", "fr") == "Non renseignée"


# --- Couverture ajoutee (ancien tests/unit) ---


def _res_mock(resource_id: str, name: str, format: str = "csv", size=2048) -> dict:
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
        "resources": [_res_mock(f"r{i}", f"Ressource {i}") for i in range(count)],
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
