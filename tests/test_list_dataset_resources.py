"""Tests unitaires pour l'outil list_dataset_resources."""

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
    assert "Dataset : Titre test" in out
    assert "ID : abc-123" in out
    assert "Slug : titre-test" in out
    assert "Organisation : Org Test" in out
    assert "Nombre de ressources : 1" in out


async def test_liste_affichage_ressource(datagov):
    async def handler(params):
        return _payload(_dataset([_resource()]))

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "1. Donnees 2024 [CSV]" in out
    assert "ID : res-1" in out
    assert "URL : https://example.org/file.csv" in out
    assert "Type : file" in out
    assert "Description : Fichier principal" in out
    assert "Datastore : actif" in out
    assert "Téléchargements : 42" in out
    assert "Taille : 2.0 Ko" in out
    assert "Modifiée le : 2024-02-01T00:00:00" in out


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
    assert "Nombre de ressources : 2" in out
    assert "1. Donnees [CSV]" in out
    assert "2. Documentation [PDF]" in out
    assert "Datastore : inactif" in out
    assert "Téléchargements : 42" in out
    assert "Créée le : 2023-01-01T00:00:00" in out
    assert "Taille : 2.0 Ko" in out


async def test_liste_sans_ressource(datagov):
    async def handler(params):
        return _payload(_dataset([]))

    datagov.handler = handler

    out = await list_dataset_resources("abc-123")
    assert "Nombre de ressources : 0" in out
    assert "Ce dataset ne contient aucune ressource." in out


async def test_liste_dataset_introuvable(datagov):
    from helpers.api_client import DatagovAPIError

    async def handler(params):
        raise DatagovAPIError("Not found: abc")

    datagov.handler = handler

    out = await list_dataset_resources("abc-introuvable")
    assert "Dataset introuvable" in out
    assert "abc-introuvable" in out


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
    assert "1. Sans nom [?]" in out
    assert "Type : Fichier" in out
    assert "Datastore : inactif" in out


def test_human_size():
    assert _human_size(500) == "500 o"
    assert _human_size(2048) == "2.0 Ko"
    assert _human_size(5 * 1024 * 1024) == "5.0 Mo"
    assert _human_size(3 * 1024 * 1024 * 1024) == "3.0 Go"
    assert _human_size(None) is None
    assert _human_size("xyz") is None
