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
