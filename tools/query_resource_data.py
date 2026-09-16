"""
Outil MCP C1 : query_resource_data (Famille C - Analyse de Donnees).
Interroge une ressource tabulaire via la Tabular API du portail
(action CKAN datastore_search / datastore_search_sql).
"""

import json
import math

from config import settings
from helpers.api_client import DatagovAPIError, datagov_client

# Operateurs de filtre autorises (CDC C1).
_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "in", "contains"}

# Operateurs traduits via datastore_search_sql : le datastore CKAN du portail
# les refuse dans le parametre "filters" (seuls eq et in y sont acceptes).
_SQL_OPERATORS = {"ne", "gt", "gte", "lt", "lte"}

# Au-dela de ce volume, un message d'avertissement est ajoute (CDC C1).
_LARGE_DATASET_ROWS = 100_000

# Types de colonnes consideres comme numeriques (litteraux non quotes en SQL).
_NUMERIC_TYPES = {
    "int",
    "integer",
    "bigint",
    "smallint",
    "serial",
    "bigserial",
    "numeric",
    "float",
    "double",
    "double precision",
    "real",
}

# Correspondance operateur -> operateur SQL.
_SQL_OPERATOR = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}

_MAX_FIELD_VALUE = 120


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _quote_column(column: str) -> str:
    """Protection des identifiants de colonnes (injection SQL)."""
    return '"' + column.replace('"', '""') + '"'


def _quote_value(value, column_type: str) -> str:
    """Litteral SQL sur pour une valeur de filtre."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if column_type in _NUMERIC_TYPES or isinstance(value, int | float):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _format_sql_value(value, column_type: str) -> str:
    """Litteral SQL pour une valeur 'in' (liste) ou un scalaire."""
    if isinstance(value, list):
        return "(" + ", ".join(_quote_value(item, column_type) for item in value) + ")"
    return _quote_value(value, column_type)


def _validate_filters(filters: list[dict] | None) -> tuple[bool, str, list[dict]]:
    """Valide et normalise la liste des filtres {column, operator, value}."""
    if not filters:
        return True, "", []

    normalized: list[dict] = []
    for index, filt in enumerate(filters, start=1):
        if not isinstance(filt, dict):
            return False, f"Filtre {index} : objet attendu (column/operator/value).", []
        column = (filt.get("column") or "").strip()
        if not column:
            return False, f"Filtre {index} : colonne manquante.", []
        operator = (filt.get("operator") or "").strip().lower()
        if operator not in _OPERATORS:
            ops = ", ".join(sorted(_OPERATORS))
            return False, f"Filtre {index} : operateur '{operator}' non autorise ({ops}).", []
        value = filt.get("value")
        if operator == "in" and not isinstance(value, list):
            return False, f"Filtre {index} : la valeur de 'in' doit etre une liste.", []
        normalized.append({"column": column, "operator": operator, "value": value})
    return True, "", normalized


def _validate_sort(sort: list[dict] | None) -> tuple[bool, str, list[dict]]:
    """Valide et normalise la liste des tris {column, direction}."""
    if not sort:
        return True, "", []

    normalized: list[dict] = []
    for index, entry in enumerate(sort, start=1):
        if not isinstance(entry, dict):
            return False, f"Tri {index} : objet attendu (column/direction).", []
        column = (entry.get("column") or "").strip()
        if not column:
            return False, f"Tri {index} : colonne manquante.", []
        direction = (entry.get("direction") or "asc").strip().lower()
        if direction not in {"asc", "desc"}:
            return False, f"Tri {index} : direction '{direction}' non autorisee (asc/desc).", []
        normalized.append({"column": column, "direction": direction})
    return True, "", normalized


def _unknown_columns(requested: list[str], available: set[str]) -> list[str]:
    return [col for col in requested if col not in available]


def _fmt_value(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= _MAX_FIELD_VALUE else text[: _MAX_FIELD_VALUE - 3] + "..."


def _sql_where(filters: list[dict], column_types: dict[str, str]) -> str:
    """Construit la clause WHERE SQL a partir des filtres valides."""
    conditions: list[str] = []
    for filt in filters:
        column = _quote_column(filt["column"])
        operator = _SQL_OPERATOR[filt["operator"]] if filt["operator"] in _SQL_OPERATOR else "="
        value = _format_sql_value(filt["value"], column_types.get(filt["column"], "text"))
        if filt["operator"] == "in":
            conditions.append(f"{column} IN {value}")
        else:
            conditions.append(f"{column} {operator} {value}")
    return " WHERE " + " AND ".join(conditions)


def _format_rows(records: list[dict], start: int) -> list[str]:
    """Affiche les enregistrements sous forme col=valeur | col=valeur."""
    lines: list[str] = []
    for i, record in enumerate(records, start=start):
        cells = [f"{key}={_fmt_value(value)}" for key, value in record.items()]
        lines.append(f"{i}. {' | '.join(cells)}")
    return lines


async def query_resource_data(
    resource_id: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    sort: list[dict] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> str:
    """
    Interroge une ressource tabulaire via la Tabular API data.gov.tn.

    Args:
        resource_id: Identifiant CKAN de la ressource (datastore actif).
        columns: Colonnes a selectionner (toutes si absentes).
        filters: Filtres sous forme d'objets {column, operator, value}.
            Operateurs autorises : eq, ne, gt, lt, gte, lte, in, contains.
        sort: Tris sous forme d'objets {column, direction} (asc/desc).
        page: Numero de page (commence a 1).
        page_size: Nombre de lignes par page (max 100).

    Returns:
        Un texte structure : schema, filtres appliques, pagination et lignes.
    """
    if not resource_id or not resource_id.strip():
        return "Veuillez fournir un identifiant de ressource."

    rid = resource_id.strip()

    ok, message, norm_filters = _validate_filters(filters)
    if not ok:
        return message
    ok, message, norm_sort = _validate_sort(sort)
    if not ok:
        return message

    # Pagination : page >= 1, page_size borne (1..MAX_PAGE_SIZE).
    page = max(1, page)
    if page_size < 1:
        page_size = 20
    else:
        page_size = min(page_size, settings.MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    # 1) Schema de la ressource (champs + types) et total de la table.
    try:
        schema = await datagov_client.get(
            "/action/datastore_search", params={"resource_id": rid, "limit": 0}
        )
    except DatagovAPIError as exc:
        return (
            f"Ressource '{rid}' non interrogeable via la Tabular API "
            f"(datastore inactif ou introuvable) : {exc}"
        )

    result = schema["result"]
    column_types = {f["id"]: f["type"] for f in result["fields"]}
    available = {col for col in column_types if col != "_full_text"}

    # 2) Validation des colonnes (selection, filtres, tris).
    requested = list(columns or [])
    requested += [f["column"] for f in norm_filters]
    requested += [f["column"] for f in norm_sort]
    unknown = _unknown_columns(requested, available)
    if unknown:
        return (
            f"Colonnes inconnues : {', '.join(sorted(set(unknown)))}. "
            f"Colonnes disponibles : {', '.join(sorted(available)) or 'aucune'}."
        )

    needs_sql = any(f["operator"] in _SQL_OPERATORS for f in norm_filters)
    has_contains = any(f["operator"] == "contains" for f in norm_filters)
    if needs_sql and has_contains:
        return (
            "L'operateur 'contains' ne peut pas etre combine avec ne/gt/lt/gte/lte "
            "(limitation de la Tabular API)."
        )

    lines: list[str] = []
    lines.append(f"Ressource : {rid}")
    lines.append(f"Schema ({len(column_types)} colonnes) :")
    for col_id, col_type in column_types.items():
        lines.append(f"  - {col_id} ({col_type})")
    lines.append("")

    for filt in norm_filters:
        value = filt["value"]
        lines.append(f"Filtre : {filt['column']} {filt['operator']} {value!r}")
    for entry in norm_sort:
        lines.append(f"Tri : {entry['column']} ({entry['direction']})")
    if norm_filters or norm_sort:
        lines.append("")

    select_columns: list[str] = []
    if columns:
        select_columns = [c for c in columns if c != "_full_text"]
    else:
        select_columns = [c for c in column_types if c != "_full_text"]

    if needs_sql:
        # Mode SQL : les operateurs de comparaison exigent datastore_search_sql.
        where = _sql_where(norm_filters, column_types)
        order = ""
        if norm_sort:
            order_terms = [
                f"{_quote_column(entry['column'])} {entry['direction'].upper()}"
                for entry in norm_sort
            ]
            order = " ORDER BY " + ", ".join(order_terms)

        sql = (
            f"SELECT {', '.join(_quote_column(c) for c in select_columns)} "
            f"FROM {_quote_column(rid)}"
            f"{where}{order} LIMIT {page_size} OFFSET {offset}"
        )
        try:
            data = await datagov_client.get("/action/datastore_search_sql", params={"sql": sql})
        except DatagovAPIError as exc:
            return f"Erreur lors de l'interrogation SQL du datastore : {exc}"

        records = data["result"]["records"]
        lines.append(f"Lignes retournees : {len(records)}")
        lines.append(f"Page {page} (total exact indisponible en mode SQL)")
    else:
        # Mode datastore_search : filtres eq/in, contains (full-text) et tri.
        params: dict = {"resource_id": rid, "limit": page_size, "offset": offset}
        if columns:
            params["fields"] = ",".join(columns)

        filters_arg: dict = {}
        q_arg: dict = {}
        for filt in norm_filters:
            if filt["operator"] == "contains":
                q_arg[filt["column"]] = filt["value"]
            else:
                filters_arg[filt["column"]] = filt["value"]
        if filters_arg:
            params["filters"] = json.dumps(filters_arg)
        if q_arg:
            params["q"] = json.dumps(q_arg)
        if norm_sort:
            sort_terms = [f"{entry['column']} {entry['direction']}" for entry in norm_sort]
            params["sort"] = ", ".join(sort_terms)

        try:
            data = await datagov_client.get("/action/datastore_search", params=params)
        except DatagovAPIError as exc:
            return f"Erreur lors de l'interrogation du datastore : {exc}"

        result = data["result"]
        total = result.get("total") or 0
        records = result.get("records") or []
        total_pages = math.ceil(total / page_size) if page_size else 1

        lines.append(f"Total : {total} ligne(s)")
        lines.append(f"Page {page}/{total_pages} ({page_size} par page)")
        if total > _LARGE_DATASET_ROWS:
            lines.append(
                f"Avertissement : dataset volumineux ({total} lignes). "
                "Interrogez par pages ou telechargez le fichier brut."
            )

    lines.append("")
    rows = _format_rows(records, start=offset + 1)
    lines.extend(rows or ["Aucune ligne trouvee."])

    return "\n".join(lines)
