from helpers.api_client import DataGovError, datagov_client
from helpers.i18n import t

_CHECKSUM_EXTRAS = ("checksum", "hash", "sha1", "sha256", "md5")


def _extras_map(resource: dict) -> dict[str, str]:
    extras = resource.get("extras") or []
    values: dict[str, str] = {}
    if isinstance(extras, dict):
        for key, value in extras.items():
            values[str(key).lower()] = str(value or "")
    else:
        for item in extras:
            if isinstance(item, dict) and item.get("key"):
                values[str(item.get("key")).lower()] = str(item.get("value") or "")
    return values


def _extract_checksum(resource: dict, lang: str) -> str:
    if resource.get("hash"):
        return str(resource["hash"])
    extras = _extras_map(resource)
    for key in _CHECKSUM_EXTRAS:
        if extras.get(key, "").strip():
            return extras[key].strip()
    return t("Non renseigné", lang)


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


def _api_error(data: dict, lang: str) -> str:
    error = data.get("error") or {}
    message = str(error.get("message") or error.get("__type") or t("Ressource introuvable.", lang))
    return f"{t('Erreur', lang)} : {message}"


def _tabular_available(resource: dict, lang: str) -> str:
    if resource.get("datastore_active"):
        return t("Oui", lang)
    return t("Non", lang)


async def _parent_title(package_id: str) -> str | None:
    try:
        data = await datagov_client.get("/action/package_show", params={"id": package_id})
    except DataGovError:
        return None
    if not data.get("success"):
        return None
    return (data.get("result") or {}).get("title")


async def get_resource_info(resource_id: str, lang: str = "fr") -> str:
    if not resource_id or not resource_id.strip():
        return t("Veuillez fournir un identifiant de ressource.", lang)
    try:
        return await _get_resource_info(resource_id, lang)
    except DataGovError as exc:
        return str(exc)


async def _get_resource_info(resource_id: str, lang: str) -> str:
    data = await datagov_client.get("/action/resource_show", params={"id": resource_id})
    if not data.get("success"):
        return _api_error(data, lang)

    resource = data["result"]
    package_id = resource.get("package_id", "")
    parent_title = await _parent_title(package_id) if package_id else None
    mimetype = resource.get("mimetype") or resource.get("mimetype_inner")

    lines: list[str] = []
    lines.append(resource.get("name") or f"{t('Ressource', lang)} {resource_id}")
    lines.append("")
    lines.append(f"{t('ID', lang)} : {resource.get('id', '')}")
    lines.append(
        f"{t('Format', lang)} : " f"{(resource.get('format') or t('Inconnu', lang)).upper()}"
    )
    lines.append(f"{t('MIME type', lang)} : {mimetype or t('Non renseigné', lang)}")
    lines.append(f"{t('URL', lang)} : {resource.get('url', t('Non renseignée', lang))}")
    lines.append(f"{t('Taille', lang)} : {_human_size(resource.get('size'), lang)}")
    lines.append(f"{t('Type de ressource', lang)} : {resource.get('resource_type') or 'file'}")
    lines.append(f"{t('Dataset parent', lang)} : {package_id or t('Non renseigné', lang)}")
    if parent_title:
        lines.append(f"   {t('Titre', lang)} : {parent_title}")
    lines.append(f"{t('Créée le', lang)} : {resource.get('created') or t('Non renseignée', lang)}")
    lines.append(
        f"{t('Dernière modification', lang)} : "
        f"{resource.get('last_modified') or t('Non renseignée', lang)}"
    )
    lines.append(f"{t('Disponibilité Tabular API', lang)} : {_tabular_available(resource, lang)}")
    lines.append(f"{t('Checksum', lang)} : {_extract_checksum(resource, lang)}")

    return "\n".join(lines)
