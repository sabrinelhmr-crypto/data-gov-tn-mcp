"""Tests unitaires pour l'outil get_dataset_info."""

from tools.get_dataset_info import get_dataset_info


def _dataset(
    dataset_id="abc-123",
    title="Titre test",
    org="Org Test",
    n_res=2,
    license="Licence ouverte",
    groups=("Theme A",),
    tags=("eau", "potable"),
    created="2023-01-01T00:00:00",
    modified="2024-02-01T00:00:00",
):
    return {
        "id": dataset_id,
        "name": "titre-test",
        "title": title,
        "type": "dataset",
        "notes": "Description du dataset.",
        "organization": {"name": "org-test", "title": org},
        "license_title": license,
        "groups": [{"display_name": g} for g in groups],
        "tags": [{"name": t} for t in tags],
        "author": "Auteur X",
        "maintainer": "Mainteneur Y",
        "metadata_created": created,
        "metadata_modified": modified,
        "url": "https://example.org/page",
        "resources": [
            {
                "id": "res-1",
                "name": "Donnees 2024",
                "format": "CSV",
                "datastore_active": True,
                "downloads_count": 42,
                "description": "Fichier principal",
                "url": "https://example.org/file.csv",
            },
            {
                "id": "res-2",
                "name": "Documentation",
                "format": "PDF",
                "datastore_active": False,
                "downloads_count": None,
                "description": "",
                "url": "https://example.org/doc.pdf",
            },
        ],
        "num_resources": 2,
        "num_tags": 2,
    }


def _payload(dataset):
    return {"success": True, "result": dataset}


async def test_info_formule_parametre_package_show(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload(_dataset())

    datagov.handler = handler

    await get_dataset_info("abc-123")
    assert captured == {"id": "abc-123"}


async def test_info_affichage_metadonnees(datagov):
    async def handler(params):
        return _payload(_dataset())

    datagov.handler = handler

    out = await get_dataset_info("abc-123")
    assert "Titre : Titre test" in out
    assert "ID : abc-123" in out
    assert "Slug : titre-test" in out
    assert "Organisation : Org Test" in out
    assert "Licence : Licence ouverte" in out
    assert "Themes : Theme A" in out
    assert "Tags : eau, potable" in out
    assert "Auteur : Auteur X" in out
    assert "Mainteneur : Mainteneur Y" in out
    assert "Crée le : 2023-01-01T00:00:00" in out
    assert "Modifié le : 2024-02-01T00:00:00" in out
    assert "URL externe : https://example.org/page" in out


async def test_info_ressources(datagov):
    async def handler(params):
        return _payload(_dataset())

    datagov.handler = handler

    out = await get_dataset_info("abc-123")
    assert "Ressources (2) :" in out
    assert "1. Donnees 2024 [CSV]" in out
    assert "res-1" in out
    assert "datastore actif" in out
    assert "42 téléchargements" in out
    assert "https://example.org/file.csv" in out
    assert "2. Documentation [PDF]" in out


async def test_info_sans_metadonnees_optionnelles(datagov):
    async def handler(params):
        return _payload(
            {
                "id": "abc-123",
                "name": "titre-test",
                "title": "Minimal",
                "notes": "",
                "organization": None,
                "resources": [],
                "num_resources": 0,
            }
        )

    datagov.handler = handler

    out = await get_dataset_info("abc-123")
    assert "Organisation : Inconnue" in out
    assert "Description : Aucune" in out
    assert "Ressources (0) :" in out
    assert "Licence :" not in out


async def test_info_dataset_introuvable(datagov):
    from helpers.api_client import DatagovAPIError

    async def handler(params):
        raise DatagovAPIError("Not found: abc")

    datagov.handler = handler

    out = await get_dataset_info("abc-introuvable")
    assert "Dataset introuvable" in out
    assert "abc-introuvable" in out


async def test_info_requete_vide(datagov):
    out = await get_dataset_info("   ")
    assert "Veuillez fournir un identifiant" in out
