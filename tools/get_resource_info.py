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

    return "\n".join(lines)
