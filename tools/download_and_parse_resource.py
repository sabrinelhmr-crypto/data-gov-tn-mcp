"""
Outil MCP C2 : download_and_parse_resource (Famille C - Analyse de Donnees).
Telecharge une ressource (CSV, Excel, JSON) et produit un apercu : schema,
statistiques descriptives et 5 premieres lignes.
"""

import io
import json
import urllib.parse

import pandas as pd

from config import settings
from helpers.api_client import DatagovAPIError, datagov_client

# Formats supportes (CDC C2) + ODS (techno simple ajoutee).
_SUPPORTED_FORMATS = {"csv", "tsv", "xlsx", "xls", "ods", "json", "geojson"}

# Engine pandas pour les formats Excel/ODS.
_EXCEL_ENGINES = {"xlsx": "openpyxl", "xls": "xlrd", "ods": "odf"}

# Nombre maximal de lignes analysees (au-dela, on refuse raisonnablement).
_MAX_LIMIT = 100_000

_SAMPLE_ROWS = 5


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _human_size(size: int | None) -> str | None:
    """Convertit une taille en octets en texte lisible (ou None si absente)."""
    if size is None:
        return None
    try:
        value = float(size)
    except (TypeError, ValueError):
        return None
    units = ["o", "Ko", "Mo", "Go", "To"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "o" else f"{int(value)} o"
        value /= 1024
    return None


def _url_extension(url: str) -> str:
    """Extension de fichier depuis une URL (sans le query string)."""
    path = urllib.parse.urlparse(url).path
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def _detect_format(resource: dict) -> str:
    """Determine le format depuis le champ 'format' puis l'extension de l'URL."""
    fmt = (resource.get("format") or "").lower().strip().lstrip(".")
    if fmt in _SUPPORTED_FORMATS:
        if fmt == "geojson":
            return "geojson"
        if fmt == "tsv":
            return "tsv"
        return fmt
    if "json" in fmt:
        return "geojson" if "geo" in fmt else "json"
    ext = _url_extension((resource.get("url") or "").lower())
    if ext in _SUPPORTED_FORMATS:
        return ext
    if ext in {"vtk", "csv.gz"}:
        return ext
    return ""


def _json_to_rows(data: bytes) -> list[dict]:
    """Convertit un payload JSON (ou GeoJSON) en liste de dictionnaires."""
    content = _decode(data)
    parsed = json.loads(content)

    if isinstance(parsed, list):
        rows = [item for item in parsed if isinstance(item, dict)]
        if not rows:
            raise ValueError("La liste JSON est vide ou ne contient pas d'objets.")
        return rows

    if not isinstance(parsed, dict):
        raise ValueError("JSON non tabulaire (liste d'objets attendue).")

    if parsed.get("type") == "FeatureCollection":
        features = parsed.get("features") or []
        rows = []
        for feature in features:
            props = dict(feature.get("properties") or {})
            geometry = feature.get("geometry")
            if geometry is not None:
                props["_geometry"] = json.dumps(geometry, ensure_ascii=False)
            rows.append(props)
        if not rows:
            raise ValueError("GeoJSON sans entites (features).")
        return rows

    for key in ("records", "data", "rows"):
        value = parsed.get(key)
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            if not rows:
                raise ValueError(f"La cle '{key}' ne contient pas d'objets.")
            return rows

    if all(
        isinstance(value, int | float | str | bool) or value is None for value in parsed.values()
    ):
        return [parsed]
    raise ValueError("JSON non tabulaire (cle 'records'/'data' attendue).")


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _read_tabular(data: bytes, file_format: str, limit: int) -> pd.DataFrame:
    """Lit le fichier brut vers un DataFrame, en limitant le nombre de lignes."""
    if file_format in {"csv", "tsv"}:
        sep = "\t" if file_format == "tsv" else ","
        return pd.read_csv(io.StringIO(_decode(data)), sep=sep, nrows=limit)
    if file_format in _EXCEL_ENGINES:
        return pd.read_excel(io.BytesIO(data), engine=_EXCEL_ENGINES[file_format])
    rows = _json_to_rows(data)
    return pd.DataFrame(rows[:limit])


def _format_cell(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    return text if len(text) <= 100 else text[:97] + "..."


def _schema_lines(df: pd.DataFrame) -> list[str]:
    return [f"  - {column} ({str(dtype)})" for column, dtype in df.dtypes.items()]


def _stats_lines(df: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for column in df.columns:
        series = df[column]
        non_null = int(series.notna().sum())
        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            lines.append(
                f"  {column} : "
                f"count={non_null:,}, "
                f"min={desc['min']:g}, "
                f"moyenne={desc['mean']:g}, "
                f"max={desc['max']:g}"
            )
        else:
            unique = int(series.nunique())
            lines.append(f"  {column} : count={non_null:,}, valeurs uniques={unique:,}")
    return lines


def _sample_lines(df: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for i, (_, row) in enumerate(df.head(_SAMPLE_ROWS).iterrows(), start=1):
        cells = [f"{column}={_format_cell(value)}" for column, value in row.items()]
        lines.append(f"{i}. {' | '.join(cells)}")
    return lines


async def download_and_parse_resource(resource_id: str, limit: int = 1000) -> str:
    """
    Telecharge et analyse une ressource (CSV, Excel, JSON, GeoJSON).

    Args:
        resource_id: Identifiant CKAN de la ressource.
        limit: Nombre maximal de lignes a analyser (defaut 1000).

    Returns:
        Un apercu : schema, statistiques descriptives et 5 premieres lignes.
    """
    if not resource_id or not resource_id.strip():
        return "Veuillez fournir un identifiant de ressource."

    rid = resource_id.strip()
    limit = max(1, min(limit, _MAX_LIMIT))

    try:
        data = await datagov_client.get("/action/resource_show", params={"id": rid})
    except DatagovAPIError as exc:
        return f"Ressource introuvable pour '{rid}' : {exc}"

    resource = data["result"]
    name = _truncate(resource.get("name") or "Sans nom", 80)
    url = resource.get("url") or ""

    file_format = _detect_format(resource)
    if not file_format:
        supported = ", ".join(sorted(_SUPPORTED_FORMATS))
        return (
            f"Ressource '{name}' : format non supporte. "
            f"Formats acceptes : {supported}. (format='{resource.get('format', '')}')"
        )

    size = resource.get("size")
    try:
        size_bytes = int(size) if size is not None else None
    except (TypeError, ValueError):
        size_bytes = None
    max_bytes = settings.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
    if size_bytes and size_bytes > max_bytes:
        return (
            f"Ressource '{name}' : fichier trop volumineux "
            f"({_human_size(size_bytes)} > {settings.MAX_DOWNLOAD_SIZE_MB} Mo)."
        )

    try:
        raw = await datagov_client.download(url)
    except DatagovAPIError as exc:
        return f"Echec du telechargement de '{name}' : {exc}"

    if len(raw) > max_bytes:
        return (
            f"Ressource '{name}' : fichier trop volumineux au telechargement "
            f"({_human_size(len(raw))} > {settings.MAX_DOWNLOAD_SIZE_MB} Mo)."
        )

    try:
        df = _read_tabular(raw, file_format, limit)
    except (ValueError, KeyError, TypeError) as exc:
        return f"Ressource '{name}' : impossible d'analyser le fichier ({exc})."
    except Exception as exc:  # pandas lève des erreurs variées selon les fichiers
        return f"Ressource '{name}' : erreur de parsing ({type(exc).__name__})."

    lines: list[str] = []
    lines.append(f"Ressource : {name}")
    lines.append(f"ID : {rid}")
    lines.append(f"Format : {file_format.upper()}")
    size_text = _human_size(size_bytes)
    if size_text:
        lines.append(f"Taille : {size_text}")
    lines.append(
        f"Lignes analysees : {len(df)}" + (f" (limite de {limit})" if len(df) >= limit else "")
    )
    lines.append("")

    if df.empty:
        lines.append("Aucune ligne a analyser.")
        return "\n".join(lines)

    lines.append(f"Schema ({len(df.columns)} colonnes) :")
    lines.extend(_schema_lines(df))
    lines.append("")
    lines.append("Statistiques descriptives :")
    lines.extend(_stats_lines(df))
    lines.append("")
    lines.append(f"{_SAMPLE_ROWS} premieres lignes :")
    lines.extend(_sample_lines(df))

    return "\n".join(lines)
