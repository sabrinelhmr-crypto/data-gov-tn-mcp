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
