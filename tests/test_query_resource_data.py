"""Tests unitaires pour l'outil query_resource_data (C1)."""

import json

from helpers.api_client import DatagovAPIError
from tools.query_resource_data import query_resource_data

RID = "res-123"

FIELDS = [
    {"id": "_id", "type": "int"},
    {"id": "Date", "type": "text"},
    {"id": "Miskar", "type": "numeric"},
]

RECORDS = [
    {"_id": 1, "Date": "2010-01", "Miskar": 127.62},
    {"_id": 2, "Date": "2010-02", "Miskar": 100.5},
]


def _payload(fields=None, total=2, records=None, limit=0):
    result = {"fields": fields or FIELDS, "total": total, "records": records or []}
    if limit:
        result["limit"] = limit
    return {"success": True, "result": result}


async def test_requete_vide(datagov):
    out = await query_resource_data("   ")
    assert "Veuillez fournir un identifiant de ressource" in out


async def test_schema_puis_interrogation(datagov):
    captured = []

    async def handler(params):
        captured.append(dict(params))
        if params.get("limit") == 0:
            return _payload()
        return _payload(records=RECORDS)

    datagov.handler = handler

    out = await query_resource_data(RID)

    assert captured[0] == {"resource_id": RID, "limit": 0}
    assert "Ressource : res-123" in out
    assert "Schema (3 colonnes) :" in out
    assert "  - Date (text)" in out
    assert "Total : 2 ligne(s)" in out
    assert "Page 1/1 (20 par page)" in out
    assert "1. _id=1 | Date=2010-01 | Miskar=127.62" in out


async def test_filtres_eq_et_in(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        captured.update(params)
        return _payload(records=RECORDS)

    datagov.handler = handler

    out = await query_resource_data(
        RID,
        filters=[
            {"column": "Date", "operator": "eq", "value": "2010-01"},
            {"column": "Miskar", "operator": "in", "value": [100, 200]},
        ],
    )

    filters_arg = json.loads(captured["filters"])
    assert filters_arg == {"Date": "2010-01", "Miskar": [100, 200]}
    assert "Filtre : Date eq '2010-01'" in out
    assert "Filtre : Miskar in [100, 200]" in out


async def test_filtre_contains_via_q(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        captured.update(params)
        return _payload(records=RECORDS)

    datagov.handler = handler

    out = await query_resource_data(
        RID, filters=[{"column": "Date", "operator": "contains", "value": "2010"}]
    )

    assert json.loads(captured["q"]) == {"Date": "2010"}
    assert "filters" not in captured
    assert "Filtre : Date contains '2010'" in out


async def test_sort_et_columns(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        captured.update(params)
        return _payload(records=RECORDS)

    datagov.handler = handler

    await query_resource_data(
        RID,
        columns=["Date", "Miskar"],
        sort=[{"column": "Miskar", "direction": "desc"}],
    )

    assert captured["fields"] == "Date,Miskar"
    assert captured["sort"] == "Miskar desc"
    assert "Tri : Miskar (desc)" in await query_resource_data(
        RID, columns=["Date"], sort=[{"column": "Miskar", "direction": "desc"}]
    )


async def test_mode_sql_operateur_ne(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        assert "sql" in params
        captured.update(params)
        return {"success": True, "result": {"records": RECORDS}}

    datagov.handler = handler

    out = await query_resource_data(
        RID, filters=[{"column": "Miskar", "operator": "ne", "value": 0}]
    )

    assert 'WHERE "Miskar" != 0' in captured["sql"]
    assert "LIMIT 20 OFFSET 0" in captured["sql"]
    assert "Lignes retournees : 2" in out
    assert "total exact indisponible en mode SQL" in out


async def test_mode_sql_gt_sort_et_echappement(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        captured.update(params)
        return {"success": True, "result": {"records": []}}

    datagov.handler = handler

    await query_resource_data(
        RID,
        filters=[
            {"column": "Miskar", "operator": "gt", "value": 100},
            {"column": "Date", "operator": "ne", "value": "O'Brien"},
        ],
        sort=[{"column": "Miskar", "direction": "desc"}],
        page=2,
        page_size=5,
    )

    sql = captured["sql"]
    assert '"Miskar" > 100' in sql
    assert "\"Date\" != 'O''Brien'" in sql
    assert 'ORDER BY "Miskar" DESC' in sql
    assert "LIMIT 5 OFFSET 5" in sql


async def test_operateur_invalide(datagov):
    async def handler(params):
        return _payload()

    datagov.handler = handler
    out = await query_resource_data(
        RID, filters=[{"column": "Date", "operator": "foo", "value": "x"}]
    )
    assert "operateur 'foo' non autorise" in out


async def test_in_valeur_non_liste(datagov):
    out = await query_resource_data(RID, filters=[{"column": "Date", "operator": "in", "value": 5}])
    assert "la valeur de 'in' doit etre une liste" in out


async def test_filtre_sans_colonne(datagov):
    out = await query_resource_data(RID, filters=[{"operator": "eq", "value": "x"}])
    assert "colonne manquante" in out


async def test_mauvais_tri(datagov):
    out = await query_resource_data(RID, sort=[{"column": "Date", "direction": "up"}])
    assert "direction 'up' non autorisee" in out


async def test_colonnes_inconnues(datagov):
    async def handler(params):
        return _payload()

    datagov.handler = handler
    out = await query_resource_data(
        RID, columns=["Bogus"], filters=[{"column": "Extra", "operator": "eq", "value": 1}]
    )
    assert "Colonnes inconnues :" in out
    assert "Extra" in out
    assert "Bogus" in out
    assert "Miskar" in out


async def test_contains_combine_sql_refuse(datagov):
    async def handler(params):
        return _payload()

    datagov.handler = handler
    out = await query_resource_data(
        RID,
        filters=[
            {"column": "Date", "operator": "contains", "value": "2010"},
            {"column": "Miskar", "operator": "ne", "value": 0},
        ],
    )
    assert "ne peut pas etre combine" in out


async def test_ressource_non_interrogeable(datagov):
    async def handler(params):
        raise DatagovAPIError("Not found: res-inconnu")

    datagov.handler = handler
    out = await query_resource_data("res-inconnu")
    assert "non interrogeable via la Tabular API" in out
    assert "res-inconnu" in out


async def test_erreur_sql(datagov):
    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        if "sql" in params:
            raise DatagovAPIError("Invalid query")

    datagov.handler = handler
    out = await query_resource_data(
        RID, filters=[{"column": "Miskar", "operator": "gt", "value": 1}]
    )
    assert "Erreur lors de l'interrogation SQL" in out


async def test_grand_dataset_avertissement(datagov):
    async def handler(params):
        if params.get("limit") == 0:
            return _payload(total=200_000)
        return _payload(total=200_000, records=[RECORDS[0]])

    datagov.handler = handler
    out = await query_resource_data(RID)
    assert "Avertissement : dataset volumineux (200000 lignes)" in out


async def test_pagination_bornee(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload(total=250)
        captured.update(params)
        return _payload(total=250, records=[])

    datagov.handler = handler
    out = await query_resource_data(RID, page=0, page_size=500)
    assert "Page 1/3 (100 par page)" in out
    assert captured["limit"] == 100
    assert captured["offset"] == 0


async def test_aucune_ligne(datagov):
    async def handler(params):
        if params.get("limit") == 0:
            return _payload(total=0)
        return _payload(total=0, records=[])

    datagov.handler = handler
    out = await query_resource_data(RID)
    assert "Aucune ligne trouvee." in out


# --- Validation des entrees de filtre et de tri ---

FIELDS_BOOL = [
    {"id": "_id", "type": "int"},
    {"id": "Date", "type": "text"},
    {"id": "Miskar", "type": "numeric"},
    {"id": "Actif", "type": "bool"},
]


async def test_filtre_pas_un_objet(datagov):
    out = await query_resource_data(RID, filters=["Date = 2010"])
    assert "objet attendu (column/operator/value)" in out


async def test_tri_pas_un_objet(datagov):
    out = await query_resource_data(RID, sort=["Date desc"])
    assert "objet attendu (column/direction)" in out


async def test_tri_sans_colonne(datagov):
    out = await query_resource_data(RID, sort=[{"direction": "desc"}])
    assert "colonne manquante" in out


async def test_erreur_datastore_hors_sql(datagov):
    """Une erreur CKAN en mode JSON doit etre rendue lisiblement."""

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        raise DatagovAPIError("Internal Server Error")

    datagov.handler = handler
    out = await query_resource_data(RID)
    assert "Erreur lors de l'interrogation du datastore" in out
    assert "Internal Server Error" in out


# --- Echappement SQL des litteraux ---


def _handler_sql(captured, fields=None):
    """Handler factice qui capture la requete SQL construite."""

    async def handler(params):
        if params.get("limit") == 0:
            return _payload(fields=fields or FIELDS_BOOL)
        captured.update(params)
        return {"success": True, "result": {"records": []}}

    return handler


async def test_null_est_ecrit_sans_guillemets(datagov):
    captured = {}
    datagov.handler = _handler_sql(captured)
    await query_resource_data(RID, filters=[{"column": "Date", "operator": "ne", "value": None}])
    assert '"Date" != NULL' in captured["sql"]


async def test_booleen_est_ecrit_en_mot_sql(datagov):
    captured = {}
    datagov.handler = _handler_sql(captured)
    await query_resource_data(RID, filters=[{"column": "Actif", "operator": "ne", "value": True}])
    assert '"Actif" != true' in captured["sql"]


async def test_operateur_in_devient_un_in_sql(datagov):
    """'in' n'est pas un operateur SQL : il n'atteint la clause WHERE que
    combine a un operateur qui, lui, force le mode SQL."""
    captured = {}
    datagov.handler = _handler_sql(captured)
    await query_resource_data(
        RID,
        filters=[
            {"column": "Miskar", "operator": "gt", "value": 0},
            {"column": "Date", "operator": "in", "value": ["2010-01", "2010-02"]},
        ],
    )
    assert '"Miskar" > 0' in captured["sql"]
    assert "\"Date\" IN ('2010-01', '2010-02')" in captured["sql"]


async def test_operateur_in_seul_passe_par_json(datagov):
    captured = {}
    datagov.handler = _handler_sql(captured)
    await query_resource_data(RID, filters=[{"column": "Date", "operator": "in", "value": ["a"]}])
    assert "sql" not in captured
    assert json.loads(captured["filters"]) == {"Date": ["a"]}


async def test_page_size_negatif_replombe_sur_20(datagov):
    captured = {}

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        captured.update(params)
        return _payload(records=RECORDS)

    datagov.handler = handler
    out = await query_resource_data(RID, page_size=0)

    assert "Page 1/1 (20 par page)" in out
    assert captured["limit"] == 20


# --- Rendu des valeurs ---


async def test_valeur_nulle_et_texte_tronque(datagov):
    long_texte = "y" * 500

    async def handler(params):
        if params.get("limit") == 0:
            return _payload()
        return _payload(
            records=[
                {"_id": 1, "Date": None, "Miskar": long_texte},
                {"_id": 2, "Date": "2010-02", "Miskar": 100.5},
            ]
        )

    datagov.handler = handler
    out = await query_resource_data(RID, columns=["_id", "Date", "Miskar"])

    ligne = next(x for x in out.splitlines() if x.startswith("1."))
    assert "Date=" in ligne
    assert "y" * 120 not in ligne
    assert "..." in ligne


def test_truncate_edeite_les_espaces():
    from tools.query_resource_data import _truncate

    assert _truncate("  court  ", 20) == "court"
    assert _truncate("abcdefghij", 5) == "ab..."
