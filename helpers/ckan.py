"""
Lecture tolerante des enveloppes de reponse CKAN.

CKAN garantit ``{"success": true, "result": ...}`` (invariant verifie par
:mod:`helpers.api_client`), mais pas la presence de chaque champ interne :
``count`` peut manquer sur une recherche sans resultat, ``fields`` sur une
ressource dont le datastore n'a pas encore de schema.

Acceder a ces cles par ``data["result"]["count"]`` transformerait une reponse
partiellement conforme en ``KeyError``, qui remonte au client MCP comme une
erreur interne opaque. Les fonctions ci-dessous renvoient une valeur
defensive, ce qui laisse l'outil rendre un message lisible.
"""

from typing import Any


def result_of(data: dict) -> dict:
    """``result`` de la reponse, garanti objet par le client HTTP."""
    result = data.get("result")
    return result if isinstance(result, dict) else {}


def search_page(data: dict) -> tuple[int, list[dict[str, Any]]]:
    """
    Extrait ``(count, results)`` d'une reponse ``package_search``.

    Si CKAN ne renvoie pas de total (indexation partielle), le nombre de
    lignes recues sert de borne basse : l'appelant affiche alors "1 resultat"
    plutot que d'echouer.
    """
    result = result_of(data)
    results = result.get("results")
    results = results if isinstance(results, list) else []

    count = result.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        count = len(results)

    return max(count, len(results)), results


def field_types(result: Any) -> dict[str, str]:
    """Table ``{nom de colonne: type}`` a partir du ``result`` d'un datastore."""
    fields = result.get("fields") if isinstance(result, dict) else None
    if not isinstance(fields, list):
        return {}
    types: dict[str, str] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        column_id = field.get("id")
        if isinstance(column_id, str):
            types[column_id] = field.get("type") or "text"
    return types
