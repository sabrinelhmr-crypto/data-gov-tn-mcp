
"""
Outil MCP B3 : get_resource_info (Famille B - Inspection et Metadonnees).
Recupere les metadonnees detaillees d'une ressource via resource_show.
"""

from helpers.api_client import DatagovAPIError, datagov_client

_MAX_DESC_LEN = 300


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


async def get_resource_info(resource_id: str) -> str:
    """
    Retourne les metadonnees detaillees d'une ressource data.gov.tn.

    Args:
        resource_id: Identifiant CKAN de la ressource (UUID).

    Returns:
        Un texte structure listant les metadonnees de la ressource.
    """
    if not resource_id or not resource_id.strip():
        return "Veuillez fournir un identifiant de ressource."

    try:
        data = await datagov_client.get("/action/resource_show", params={"id": resource_id.strip()})
    except DatagovAPIError as exc:
        return f"Ressource introuvable pour '{resource_id.strip()}' : {exc}"

    res = data["result"]

    lines: list[str] = []
    lines.append(f"Ressource : {_truncate(res.get('name') or 'Sans nom', 80)}")
    lines.append(f"ID : {res.get('id', '')}")

    if res.get("package_id"):
        lines.append(f"Dataset : {res['package_id']}")

    res_format = (res.get("format") or "?").upper()
    lines.append(f"Format : {res_format}")

    if res.get("mimetype"):
        lines.append(f"Type MIME : {res['mimetype']}")

    description = _truncate(res.get("description") or "", _MAX_DESC_LEN)
    lines.append(f"Description : {description or 'Aucune'}")

    res_type = res.get("resource_type") or "Fichier"
    lines.append(f"Type : {res_type}")

    if res.get("url"):
        lines.append(f"URL : {res['url']}")

    datastore = "actif" if res.get("datastore_active") else "inactif"
    lines.append(f"Datastore : {datastore}")

    downloads = res.get("downloads_count")
    if downloads is not None:
        lines.append(f"Téléchargements : {downloads}")

    if res.get("last_modified"):
        lines.append(f"Modifiée le : {res['last_modified']}")

    if res.get("created"):
        lines.append(f"Créée le : {res['created']}")

    size = _human_size(res.get("size"))
    if size:
        lines.append(f"Taille : {size}")

    if res.get("revision_timestamp"):
        lines.append(f"Révision : {res['revision_timestamp']}")
=======
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
