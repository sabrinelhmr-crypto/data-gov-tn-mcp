"""Tests unitaires pour l'outil search_dataservices."""

from tools.search_dataservices import search_dataservices


def _dataset(
    dataset_id="abc-123",
    title="API Meteo",
    org="Ministere Environnement",
    fmt="WFS",
    res_url="https://api.example.org/meteo",
    notes="Service meteo national.",
    modified="2024-01-15T00:00:00",
):
    return {
        "id": dataset_id,
        "title": title,
        "organization": {"name": "min-env", "title": org},
        "notes": notes,
        "metadata_modified": modified,
        "num_resources": 1,
        "resources": [
            {
                "id": "res-1",
                "name": "Service Meteo",
                "format": fmt,
                "url": res_url,
            }
        ],
    }


def _payload(datasets, count=None):
    return {
        "success": True,
        "result": {
            "count": len(datasets) if count is None else count,
            "results": datasets,
        },
    }


async def test_formule_parametres_ckan(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset()])

    datagov.handler = handler
    out = await search_dataservices("meteo")
    assert captured["q"] == "meteo"
    assert captured["rows"] == 20
    assert captured["start"] == 0
    assert "API Meteo" in out


async def test_affichage_service(datagov):
    async def handler(params):
        return _payload([_dataset()])

    datagov.handler = handler
    out = await search_dataservices("meteo")
    assert "abc-123" in out
    assert "Ministere Environnement" in out
    assert "Service : Service Meteo [WFS]" in out
    assert "https://api.example.org/meteo" in out
    assert "Service meteo national." in out
    assert "2024-01-15T00:00:00" in out


async def test_dataset_sans_ressource_service(datagov):
    async def handler(params):
        ds = _dataset(fmt="PDF", res_url="")
        ds["num_resources"] = 2
        return _payload([ds])

    datagov.handler = handler
    out = await search_dataservices("meteo")
    assert "Service :" not in out
    assert "Ressources : 2" in out


async def test_aucun_resultat(datagov):
    async def handler(params):
        return _payload([])

    datagov.handler = handler
    out = await search_dataservices("zzz introuvable")
    assert "Aucun resultat" in out


async def test_requete_vide(datagov):
    out = await search_dataservices("   ")
    assert "Veuillez fournir une requete" in out


async def test_filtre_organisation(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset()])

    datagov.handler = handler
    await search_dataservices("meteo", organization="ministere")
    assert captured["fq"] == "organization:ministere"


async def test_filtre_organisation_et_tags(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset()])

    datagov.handler = handler
    await search_dataservices("meteo", organization="ministere", tags=["climat", "api"])
    assert captured["fq"] == "organization:ministere AND tags:climat AND tags:api"


async def test_fallback_requete_originale(datagov):
    calls = []

    async def handler(params):
        calls.append(params["q"])
        if params["q"] == "donnees csv meteo":
            return _payload([_dataset(title="Meteo nationale")])
        return _payload([])

    datagov.handler = handler
    out = await search_dataservices("donnees csv meteo")
    assert calls == ["meteo", "donnees csv meteo"]
    assert "Meteo nationale" in out


async def test_reduction_progressive(datagov):
    calls = []

    async def handler(params):
        calls.append(params["q"])
        if params["q"] == "meteo":
            return _payload([_dataset(title="Aggregateur meteo")])
        return _payload([])

    datagov.handler = handler
    out = await search_dataservices("meteo transport tunisie")
    assert calls == ["meteo transport tunisie", "meteo transport", "meteo"]
    assert "Aggregateur meteo" in out


async def test_borne_page_size(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([])

    datagov.handler = handler
    await search_dataservices("meteo", page_size=500)
    assert captured["rows"] == 100
