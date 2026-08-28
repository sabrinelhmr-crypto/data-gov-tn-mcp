"""
Outil MCP A2 : get_dataset_info (section 4.2 du CDC).
Affiche les metadonnees detaillees d'un dataset via package_show.
"""

from helpers.api_client import DatagovAPIError, datagov_client

_MAX_DESC_LEN = 300


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


async def get_dataset_info(dataset_id: str) -> str:
    """
    Retourne des metadonnees detaillees sur un dataset data.gov.tn.

    Args:
        dataset_id: Identifiant CKAN du dataset (UUID) ou slug (name).

    Returns:
        Un texte structure listant les metadonnees et les ressources.
    """
    if not dataset_id or not dataset_id.strip():
        return "Veuillez fournir un identifiant de dataset."

    try:
        data = await datagov_client.get("/action/package_show", params={"id": dataset_id.strip()})
    except DatagovAPIError as exc:
        return f"Dataset introuvable pour '{dataset_id.strip()}' : {exc}"

    d = data["result"]

    lines: list[str] = []
    lines.append(f"Titre : {d.get('title', 'Sans titre')}")
    lines.append(f"ID : {d.get('id', '')}")
    lines.append(f"Slug : {d.get('name', '')}")
    lines.append(f"Type : {d.get('type', 'dataset')}")

    description = _truncate(d.get("notes") or "", _MAX_DESC_LEN)
    lines.append(f"Description : {description or 'Aucune'}")

    organisation = (d.get("organization") or {}).get("title") or "Inconnue"
    lines.append(f"Organisation : {organisation}")

    if d.get("license_title"):
        lines.append(f"Licence : {d['license_title']}")

    groups = [g.get("display_name", "") for g in d.get("groups") or []]
    if groups:
        lines.append(f"Themes : {', '.join(groups)}")

    tags = [t.get("name", "") for t in d.get("tags") or []]
    if tags:
        lines.append(f"Tags : {', '.join(tags)}")

    for label, key in (("Auteur", "author"), ("Mainteneur", "maintainer")):
        value = (d.get(key) or "").strip()
        if value:
            lines.append(f"{label} : {value}")

    for label, key in (("Crée le", "metadata_created"), ("Modifié le", "metadata_modified")):
        if d.get(key):
            lines.append(f"{label} : {d[key]}")

    if d.get("url"):
        lines.append(f"URL externe : {d['url']}")

    lines.append("")

    resources = d.get("resources") or []
    lines.append(f"Ressources ({len(resources)}) :")
    for i, res in enumerate(resources, start=1):
        res_name = _truncate(res.get("name") or "Sans nom", 80)
        res_format = (res.get("format") or "?").upper()
        line = f"{i}. {res_name} [{res_format}]"
        details: list[str] = [res.get("id", "")]
        if res.get("datastore_active"):
            details.append("datastore actif")
        downloads = res.get("downloads_count")
        if downloads is not None:
            details.append(f"{downloads} téléchargements")
        if res.get("description"):
            details.append(_truncate(res["description"], 80))
        lines.append(f"   {line} ({', '.join(details)})")
        if res.get("url"):
            lines.append(f"   URL : {res['url']}")

    # Statistiques generales
    lines.append("")
    if d.get("num_resources") is not None:
        lines.append(f"Nombre de ressources : {d['num_resources']}")
    if d.get("num_tags") is not None:
        lines.append(f"Nombre de tags : {d['num_tags']}")

    return "\n".join(lines)
