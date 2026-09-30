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
