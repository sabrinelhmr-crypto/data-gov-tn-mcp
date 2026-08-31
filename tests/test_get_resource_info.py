"""Tests unitaires pour l'outil get_resource_info."""

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
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload(_resource())

    datagov.handler = handler

    await get_resource_info("res-1")
    assert captured == {"id": "res-1"}


async def test_info_affichage_metadonnees(datagov):
    async def handler(params):
        return _payload(_resource())

    datagov.handler = handler

    out = await get_resource_info("res-1")
    assert "Ressource : Donnees 2024" in out
    assert "ID : res-1" in out
    assert "Dataset : abc-123" in out
    assert "Format : CSV" in out
    assert "Type MIME : text/csv" in out
    assert "Type : file" in out
    assert "Description : Fichier principal" in out
    assert "URL : https://example.org/file.csv" in out
    assert "Datastore : actif" in out
    assert "Téléchargements : 42" in out
    assert "Modifiée le : 2024-02-01T00:00:00" in out
    assert "Créée le : 2023-01-01T00:00:00" in out
    assert "Taille : 2.0 Ko" in out
    assert "Révision : 2024-02-01T00:00:00" in out


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
    assert "Ressource : Sans nom" in out
    assert "Format : ?" in out
    assert "Type : Fichier" in out
    assert "Datastore : inactif" in out
    assert "Description : Aucune" in out
    assert "Dataset :" not in out
    assert "Téléchargements :" not in out


async def test_info_ressource_introuvable(datagov):
    from helpers.api_client import DatagovAPIError

    async def handler(params):
        raise DatagovAPIError("Not found: res-inconnu")

    datagov.handler = handler

    out = await get_resource_info("res-inconnu")
    assert "Ressource introuvable" in out
    assert "res-inconnu" in out


async def test_info_requete_vide(datagov):
    out = await get_resource_info("   ")
    assert "Veuillez fournir un identifiant de ressource" in out


def test_human_size():
    assert _human_size(500) == "500 o"
    assert _human_size(2048) == "2.0 Ko"
    assert _human_size(5 * 1024 * 1024) == "5.0 Mo"
    assert _human_size(None) is None
    assert _human_size("xyz") is None
