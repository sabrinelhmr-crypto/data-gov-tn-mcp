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


# --- Bornes de pagination ---


async def test_page_size_negatif_replombe_sur_20(datagov):
    """Un page_size < 1 ne doit pas produire une page vide."""
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau", page_size=0)

    assert capture["rows"] == 20


async def test_page_size_trop_grand_est_plafonne(datagov):
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau", page_size=5000)

    assert capture["rows"] == 100


async def test_page_negative_est_ramene_a_1(datagov):
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau", page=-3)

    assert capture["start"] == 0


# --- Filtres fq (organisation / tags) ---


async def test_filtre_organisation_est_transmis(datagov):
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau", organization="ministere")

    assert capture["fq"] == "organization:ministere"


async def test_filtres_tags_sont_combines_avec_et(datagov):
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau", tags=["sante", "hopital"])

    assert capture["fq"] == "tags:sante AND tags:hopital"


async def test_organisation_et_tags_se_combinent(datagov):
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau", organization="ministere", tags=["sante"])

    assert capture["fq"] == "organization:ministere AND tags:sante"


async def test_aucun_filtre_ne_renvoie_pas_fq(datagov):
    capture = {}

    async def handler(params):
        capture.update(params)
        return _ok([_dataset()])

    datagov.handler = handler
    await search_datasets("eau")

    assert "fq" not in capture


# --- Repli sur la requete d'origine, puis reduction progressive ---


async def test_repli_sur_la_requete_non_nettoyee(datagov):
    """Si la requete nettoyee ne donne rien, on retente la requete brute."""
    vues = []

    async def handler(params):
        vues.append(params["q"])
        if params["q"] == "donnees prix":
            return _ok([_dataset(title="Dataset Prix")])
        return _ok([])

    datagov.handler = handler
    out = await search_datasets("donnees prix")

    assert vues == ["prix", "donnees prix"]
    assert "Dataset Prix" in out
    # Le repli utilise la requete d'origine : rien n'est annonce comme elargi.
    assert "Recherche elargie" not in out


async def test_reduction_progressive_des_mots(datagov):
    """En cas d'echec total, les mots sont retires un par un a droite."""
    vues = []

    async def handler(params):
        vues.append(params["q"])
        if params["q"] == "eau potable tunisie":
            return _ok([])
        if params["q"] == "eau potable":
            return _ok([_dataset(title="Dataset Eau")])
        return _ok([])

    datagov.handler = handler
    out = await search_datasets("eau potable tunisie")

    assert vues[0] == "eau potable tunisie"
    assert "eau potable" in vues
    assert "Dataset Eau" in out
    assert "Recherche elargie : requete reduite a 'eau potable'" in out


async def test_reduction_progressive_s_arrete_au_premier_succes(datagov):
    vues = []

    async def handler(params):
        vues.append(params["q"])
        return _ok([])

    datagov.handler = handler
    await search_datasets("eau potable tunisie")

    # Sans succes, chaque reduction est tentee : "eau potable tunisie",
    # puis "eau potable", puis "eau".
    assert vues == ["eau potable tunisie", "eau potable", "eau"]


# --- Rendu ---


async def test_description_longue_est_tronquee(datagov):
    async def handler(params):
        d = _dataset()
        d["notes"] = "x" * 400
        return _ok([d])

    datagov.handler = handler
    out = await search_datasets("eau")

    ligne = next(x for x in out.splitlines() if "Description" in x)
    assert ligne.rstrip().endswith("...")
    assert len(ligne) < 200
