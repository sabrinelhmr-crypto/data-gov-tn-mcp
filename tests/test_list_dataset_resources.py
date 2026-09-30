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
