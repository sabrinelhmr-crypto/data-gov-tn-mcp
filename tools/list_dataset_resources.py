
"""
Outil MCP B2 : list_dataset_resources (Famille B - Inspection et Metadonnees).
Liste les ressources (fichiers) attachees a un dataset via package_show.
"""

from helpers.api_client import DatagovAPIError, datagov_client

_MAX_DESC_LEN = 120


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


async def list_dataset_resources(dataset_id: str) -> str:
    """
    Liste les ressources (fichiers) attachees a un dataset data.gov.tn.

    Args:
        dataset_id: Identifiant CKAN du dataset (UUID) ou slug (name).

    Returns:
        Un texte structure listant chaque ressource (format, type, URL, ...).
    """
    if not dataset_id or not dataset_id.strip():
        return "Veuillez fournir un identifiant de dataset."

    try:
        data = await datagov_client.get("/action/package_show", params={"id": dataset_id.strip()})
    except DatagovAPIError as exc:
        return f"Dataset introuvable pour '{dataset_id.strip()}' : {exc}"

    d = data["result"]
    resources = d.get("resources") or []

    lines: list[str] = []
    lines.append(f"Dataset : {d.get('title', 'Sans titre')}")
    lines.append(f"ID : {d.get('id', '')}")
    if d.get("name"):
        lines.append(f"Slug : {d.get('name')}")
    organisation = (d.get("organization") or {}).get("title") or "Inconnue"
    lines.append(f"Organisation : {organisation}")
    lines.append(f"Nombre de ressources : {len(resources)}")
    lines.append("")

    if not resources:
        lines.append("Ce dataset ne contient aucune ressource.")
        return "\n".join(lines)

    for i, res in enumerate(resources, start=1):
        res_name = _truncate(res.get("name") or "Sans nom", 80)
        res_format = (res.get("format") or "?").upper()

        lines.append(f"{i}. {res_name} [{res_format}]")
        lines.append(f"   ID : {res.get('id', '')}")

        if res.get("url"):
            lines.append(f"   URL : {res['url']}")

        res_type = res.get("resource_type") or "Fichier"
        lines.append(f"   Type : {res_type}")

        if res.get("description"):
            lines.append(f"   Description : {_truncate(res['description'], _MAX_DESC_LEN)}")

        datastore = "actif" if res.get("datastore_active") else "inactif"
        lines.append(f"   Datastore : {datastore}")

        downloads = res.get("downloads_count")
        if downloads is not None:
            lines.append(f"   Téléchargements : {downloads}")

        size = _human_size(res.get("size"))
        if size:
            lines.append(f"   Taille : {size}")

        if res.get("last_modified"):
            lines.append(f"   Modifiée le : {res['last_modified']}")
        elif res.get("created"):
            lines.append(f"   Créée le : {res['created']}")

        lines.append("")

    return "\n".join(lines).rstrip("\n")
=======
import math

from config import settings
from helpers.api_client import DataGovError, datagov_client
from helpers.i18n import t


def _human_size(size, lang: str) -> str:
    if size is None:
        return t("Non renseignée", lang)
    try:
        value = float(size)
    except (TypeError, ValueError):
        return t("Non renseignée", lang)
    units = ("o", "Ko", "Mo", "Go")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} o"
    return f"{value:.1f} {units[index]}"


def _api_error(data: dict, dataset_id: str, lang: str) -> str:
    error = data.get("error") or {}
    message = str(error.get("message") or error.get("__type") or t("Dataset introuvable.", lang))
    return f"{t('Erreur', lang)} : {message} (dataset {dataset_id})"


async def list_dataset_resources(
    dataset_id: str, page: int = 1, page_size: int = 20, lang: str = "fr"
) -> str:
    if not dataset_id or not dataset_id.strip():
        return t("Veuillez fournir un identifiant de dataset.", lang)
    try:
        return await _list_dataset_resources(dataset_id, page, page_size, lang)
    except DataGovError as exc:
        return str(exc)


async def _list_dataset_resources(dataset_id: str, page: int, page_size: int, lang: str) -> str:
    if page_size < 1:
        page_size = 20
    else:
        page_size = min(page_size, settings.MAX_PAGE_SIZE)
    page = max(1, page)

    data = await datagov_client.get("/action/package_show", params={"id": dataset_id})
    if not data.get("success"):
        return _api_error(data, dataset_id, lang)

    package = data["result"]
    resources = package.get("resources") or []
    total = len(resources)
    if total == 0:
        return t("Aucune ressource attachée à ce dataset.", lang)

    total_pages = math.ceil(total / page_size)
    start = (page - 1) * page_size
    end = start + page_size
    page_resources = resources[start:end]

    lines: list[str] = []
    title = package.get("title") or dataset_id
    lines.append(f"{total} {t('ressource(s) pour', lang)} '{title}' :")
    lines.append(f"{t('Page', lang)} {page}/{total_pages} ({page_size} {t('par page', lang)})")
    lines.append("")

    for i, resource in enumerate(page_resources, start=start + 1):
        name = resource.get("name") or f"{t('Ressource', lang)} {i}"
        lines.append(f"{i}. {name}")
        lines.append(f"   {t('ID', lang)} : {resource.get('id', '')}")
        lines.append(
            f"   {t('Format', lang)} : " f"{(resource.get('format') or t('Inconnu', lang)).upper()}"
        )
        lines.append(f"   {t('Taille', lang)} : {_human_size(resource.get('size'), lang)}")
        lines.append(f"   {t('Type', lang)} : {resource.get('resource_type') or 'file'}")
        lines.append(f"   {t('URL', lang)} : {resource.get('url', t('Non renseignée', lang))}")
        lines.append(
            f"   {t('Dernière modification', lang)} : "
            f"{resource.get('last_modified') or t('Non renseignée', lang)}"
        )
        tabular = t("Oui", lang) if resource.get("datastore_active") else t("Non", lang)
        lines.append(f"   {t('Tabular API', lang)} : {tabular}")
        lines.append("")

    return "\n".join(lines)

