"""Tests unitaires pour l'outil get_resource_info."""

from unittest.mock import AsyncMock, patch

from tools.get_resource_info import _human_size, get_resource_info


def _resource(**overrides):
    values = {
        "id": "res-1",
        "package_id": "abc-123",
        "name": "Donnees 2024",
        "format": "CSV",
        "mimetype": "text/csv",
        "url": "https://example.org/file.csv",
        "resource_type": "file",
        "description": "Fichier principal",
        "datastore_active": True,
        "downloads_count": 42,
        "size": 2048,
        "created": "2023-01-01T00:00:00",
        "last_modified": "2024-02-01T00:00:00",
        "revision_timestamp": "2024-02-01T00:00:00",
    }
    values.update(overrides)
    return values


def _payload(resource):
    return {"success": True, "result": resource}


async def test_info_formule_parametre_resource_show(datagov):
    calls = []

    async def path_handler(path, params):
        calls.append((path, dict(params)))
        if path == "/action/resource_show":
            return _payload(_resource())
        return _payload({"id": "abc-123", "title": "Titre parent"})

    datagov.path_handler = path_handler

    await get_resource_info("res-1")
    assert calls[0] == ("/action/resource_show", {"id": "res-1"})


async def test_info_affichage_metadonnees(datagov):
    async def path_handler(path, params):
        if path == "/action/resource_show":
            return _payload(_resource())
        return _payload({"id": "abc-123", "title": "Titre parent"})

    datagov.path_handler = path_handler

    out = await get_resource_info("res-1")
    assert out.splitlines()[0] == "Donnees 2024"
    assert "ID : res-1" in out
    assert "Dataset parent : abc-123" in out
    assert "   Titre : Titre parent" in out
    assert "Format : CSV" in out
    assert "MIME type : text/csv" in out
    assert "Type de ressource : file" in out
    assert "URL : https://example.org/file.csv" in out
    assert "Disponibilité Tabular API : Oui" in out
    assert "Dernière modification : 2024-02-01T00:00:00" in out
    assert "Créée le : 2023-01-01T00:00:00" in out
    assert "Taille : 2.0 Ko" in out
    # Le nombre de telechargements et l'horodatage de revision ne sont plus
    # exposes : le portail ne les garantit pas pour toutes les ressources.
    assert "Téléchargements :" not in out
    assert "Révision :" not in out


async def test_info_sans_metadonnees_optionnelles(datagov):
    async def handler(params):
        return _payload(
            {
                "id": "res-min",
                "name": "",
                "format": "",
                "url": "",
                "datastore_active": False,
            }
        )

    datagov.handler = handler

    out = await get_resource_info("res-min")
    assert out.splitlines()[0] == "Ressource res-min"
    assert "Format : INCONNU" in out
    assert "Type de ressource : file" in out
    assert "Disponibilité Tabular API : Non" in out
    assert "Taille : Non renseignée" in out
    assert "Dataset parent : Non renseigné" in out
    assert "Description :" not in out
    assert "Téléchargements :" not in out


async def test_info_ressource_introuvable(datagov):
    from helpers.api_client import DatagovAPIError

    async def handler(params):
        raise DatagovAPIError("Not found: res-inconnu")

    datagov.handler = handler

    out = await get_resource_info("res-inconnu")
    assert "Not found: res-inconnu" in out


async def test_info_requete_vide(datagov):
    out = await get_resource_info("   ")
    assert "Veuillez fournir un identifiant de ressource" in out


def test_human_size():
    assert _human_size(500, "fr") == "500 o"
    assert _human_size(2048, "fr") == "2.0 Ko"
    assert _human_size(5 * 1024 * 1024, "fr") == "5.0 Mo"
    assert _human_size(None, "fr") == "Non renseignée"
    assert _human_size("xyz", "fr") == "Non renseignée"


# --- Couverture ajoutee (ancien tests/unit) ---


def _res_mock() -> dict:
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
        side_effect=[_show_response(_res_mock()), _package_show_response("Population")]
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
    res = _res_mock()
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
            _show_response(_res_mock()),
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
        side_effect=[_show_response(_res_mock()), _package_show_response("Population")]
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
        side_effect=[_show_response(_res_mock()), _package_show_response("Population")]
    )
    with patch("tools.get_resource_info.datagov_client.get", mock):
        result = await get_resource_info("res1", lang="ar")
    assert "مجموعة البيانات الأصلية" in result
    assert "المجموع الاختباري" in result
