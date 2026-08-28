"""Tests unitaires pour l'outil search_datasets et le nettoyage de requete."""

from helpers.query_cleaner import clean_query
from tools.search_datasets import search_datasets

# --- helpers.query_cleaner ------------------------------------------------


def test_clean_query_retire_les_termes_generiques():
    assert clean_query("donnees fichier csv prix immobilier") == "prix immobilier"


def test_clean_query_insensible_aux_accents():
    assert clean_query("Données excel Tableau logement") == "logement"


def test_clean_query_sans_terme_generique():
    assert clean_query("prix immobilier tunisie") == "prix immobilier tunisie"


def test_clean_query_uniquement_generique():
    assert clean_query("csv json xml") == ""


def test_clean_query_vide():
    assert clean_query("") == ""
    assert clean_query(None) == ""


# --- outils : search_datasets --------------------------------------------


def _dataset(
    dataset_id="abc-123",
    title="Titre test",
    org="Org Test",
    n_res=2,
    modified="2023-01-01T00:00:00",
    tags=("tag1",),
):
    return {
        "id": dataset_id,
        "title": title,
        "organization": {"name": "org-test", "title": org},
        "num_resources": n_res,
        "metadata_modified": modified,
        "tags": [{"name": t} for t in tags],
        "notes": "Description courte",
    }


def _payload(results, count=None):
    return {
        "success": True,
        "result": {
            "count": len(results) if count is None else count,
            "results": results,
        },
    }


async def test_search_formule_les_parametres_ckan(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset()])

    datagov.handler = handler

    out = await search_datasets("prix immobilier", page=2, page_size=10)
    assert captured["q"] == "prix immobilier"
    assert captured["rows"] == 10
    assert captured["start"] == 10
    assert out.startswith("1 resultat(s)")


async def test_search_fallback_requete_originale(datagov):
    calls = []

    async def handler(params):
        calls.append(params["q"])
        if params["q"] == "prix immobilier":  # requete nettoyee (identique ici)
            return _payload([])
        return _payload([_dataset()])

    datagov.handler = handler

    out = await search_datasets("prix immobilier donnees csv")
    assert calls == ["prix immobilier", "prix immobilier donnees csv"]
    assert "Titre test" in out


async def test_search_aucun_resultat_meme_apres_reduction(datagov):
    calls = []

    async def handler(params):
        calls.append(params["q"])
        return _payload([])

    datagov.handler = handler

    out = await search_datasets("prix immobilier")
    assert calls == ["prix immobilier", "prix"]
    assert "Aucun resultat" in out


async def test_search_reduction_progressive_et_indication(datagov):
    calls = []

    async def handler(params):
        calls.append(params["q"])
        if params["q"] == "prix":
            return _payload([_dataset()])
        return _payload([])

    datagov.handler = handler

    out = await search_datasets("prix immobilier tunisie")
    assert calls == ["prix immobilier tunisie", "prix immobilier", "prix"]
    assert "Recherche elargie" in out
    assert "requete reduite a 'prix'" in out
    assert "Titre test" in out


async def test_search_sans_resultat(datagov):
    async def handler(params):
        return _payload([])

    datagov.handler = handler
    out = await search_datasets("zzzz inconnu")
    assert out == "Aucun resultat trouve pour 'zzzz inconnu'."


async def test_search_bounde_page_size_a_max(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset(), _dataset()])

    datagov.handler = handler

    await search_datasets("xyz", page_size=500)
    assert captured["rows"] == 100


async def test_search_page_minimum_bornne(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset()])

    datagov.handler = handler

    await search_datasets("xyz", page=0, page_size=0)
    assert captured["start"] == 0
    assert captured["rows"] == 20


async def test_search_filtres_organisation_et_tags(datagov):
    captured = {}

    async def handler(params):
        captured.update(params)
        return _payload([_dataset()])

    datagov.handler = handler

    await search_datasets("xyz", organization="ministere", tags=["sante", "hopital"])
    assert captured["fq"] == "organization:ministere AND tags:sante AND tags:hopital"


async def test_search_informations_pagination(datagov):
    async def handler(params):
        return _payload([_dataset() for _ in range(5)], count=25)

    datagov.handler = handler
    out = await search_datasets("xyz", page=2, page_size=10)
    assert "25 resultat(s)" in out
    assert "Page 2/3 (10 par page)" in out


async def test_search_formatage_resultat(datagov):
    async def handler(params):
        return _payload(
            [
                _dataset(
                    dataset_id="abc-123",
                    title="Prix terrains",
                    org="Ministere A",
                    n_res=3,
                    modified="2024-02-01T00:00:00",
                    tags=("a", "b"),
                ),
            ]
        )

    datagov.handler = handler
    out = await search_datasets("prix")
    assert "Prix terrains" in out
    assert "abc-123" in out
    assert "Ministere A" in out
    assert "ressources: 3" in out
    assert "2024-02-01T00:00:00" in out
    assert "a, b" in out


async def test_search_requete_vide(datagov):
    out = await search_datasets("   ")
    assert "Veuillez fournir une requete" in out
