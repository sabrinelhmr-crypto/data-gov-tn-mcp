"""Tests simples pour la recherche de datasets."""

from helpers.query_cleaner import clean_query
from tools.search_datasets import search_datasets


def _dataset(title="Dataset test", dataset_id="abc-123", n_res=2):
    return {
        "id": dataset_id,
        "title": title,
        "organization": {"name": "org-test", "title": "Organisation Test"},
        "num_resources": n_res,
        "metadata_modified": "2024-01-15T00:00:00",
        "tags": [{"name": "economie"}],
        "notes": "Description du dataset",
    }


def _ok(results, count=None):
    return {
        "success": True,
        "result": {
            "count": len(results) if count is None else count,
            "results": results,
        },
    }


# --- Nettoyage de requete ---


def test_nettoyage_supprime_termes_inutiles():
    assert clean_query("donnees csv prix immobilier") == "prix immobilier"


def test_nettoyage_garde_les_mots_cles():
    assert clean_query("eau potable tunisie") == "eau potable tunisie"


def test_nettoyage_requete_vide():
    assert clean_query("") == ""


# --- Recherche simple ---


async def test_recherche_reussie(datagov):
    async def handler(params):
        return _ok([_dataset(title="Prix immobilier Tunis")])

    datagov.handler = handler
    out = await search_datasets("prix immobilier")
    assert "Prix immobilier Tunis" in out
    assert "1 resultat(s)" in out


async def test_recherche_aucun_resultat(datagov):
    async def handler(params):
        return _ok([])

    datagov.handler = handler
    out = await search_datasets("terme inexistant xyz")
    assert "Aucun resultat" in out


async def test_requete_vide_renvoie_erreur(datagov):
    out = await search_datasets("   ")
    assert "Veuillez fournir une requete" in out


# --- Recherche avec mot-clé utilisateur ---


async def test_recherche_par_mot_cle_utilisateur(datagov):
    async def handler(params):
        if params["q"] == "education":
            return _ok([_dataset(title="Statistiques education")])
        return _ok([])

    datagov.handler = handler
    out = await search_datasets("education")
    assert "Statistiques education" in out


async def test_recherche_plusieurs_resultats(datagov):
    async def handler(params):
        return _ok(
            [
                _dataset(title="Dataset A"),
                _dataset(title="Dataset B"),
                _dataset(title="Dataset C"),
            ]
        )

    datagov.handler = handler
    out = await search_datasets("sante")
    assert "Dataset A" in out
    assert "Dataset B" in out
    assert "Dataset C" in out
    assert "3 resultat(s)" in out
