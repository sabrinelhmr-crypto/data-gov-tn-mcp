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
    assert out.splitlines()[0] == "Titre test"
    assert "ID : abc-123" in out
    assert "Organisation : Org Test" in out
    assert "Description : Description du dataset." in out
    assert "Licence : Licence ouverte" in out
    assert "Tags : eau, potable" in out
    assert "Créé le : 2023-01-01T00:00:00" in out
    assert "Dernière modification : 2024-02-01T00:00:00" in out
    assert "Nombre de ressources : 2" in out


async def test_info_ressources(datagov):
    async def handler(params):
        return _payload(_dataset())

    datagov.handler = handler

    out = await get_dataset_info("abc-123")
    # Les ressources sont resumees par leur nombre ; le detail est expose par
    # list_dataset_resources (B2) et get_resource_info (B3).
    assert "Nombre de ressources : 2" in out
    assert "Qualité des métadonnées : 88%" in out
    assert "Champs manquants : fréquence de mise à jour" in out
    assert "Ressources (" not in out


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
    assert out.splitlines()[0] == "Minimal"
    assert "Organisation : Organisation inconnue" in out
    assert "Licence : Non renseignée" in out
    assert "Nombre de ressources : 0" in out
    # Une description absente ne produit aucune ligne, et la licence est
    # toujours presente (avec sa valeur de repli).
    assert "Description :" not in out
    assert "Qualité des métadonnées : 12%" in out


async def test_info_dataset_introuvable(datagov):
    from helpers.api_client import DatagovAPIError

    async def handler(params):
        raise DatagovAPIError("Not found: abc")

    datagov.handler = handler

    out = await get_dataset_info("abc-introuvable")
    assert "Not found: abc" in out


async def test_info_metadonnees_cdc(datagov):
    ds = _dataset()
    ds["extras"] = [{"key": "frequency", "value": "mensuelle"}]
    ds.pop("url")

    async def handler(params):
        return _payload(ds)

    datagov.handler = handler
    out = await get_dataset_info("abc-123")
    assert "Fréquence de mise à jour : mensuelle" in out
    assert "Qualité des métadonnées : 100%" in out
    assert "Champs manquants" not in out


async def test_info_requete_vide(datagov):
    out = await get_dataset_info("   ")
    assert "Veuillez fournir un identifiant" in out
