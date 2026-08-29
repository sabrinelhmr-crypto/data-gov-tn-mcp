"""
Outil MCP A1 : search_datasets (Famille A - Recherche et Decouverte).
Version connectee a la vraie API : https://catalog.data.gov.tn
"""

import math

from config import settings
from helpers.api_client import datagov_client
from helpers.query_cleaner import clean_query


async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
    organization: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Recherche des jeux de donnees sur data.gov.tn par mots-cles.

    Args:
        query: Termes de recherche (ex: "eau potable")
        page: Numero de page (commence a 1)
        page_size: Nombre de resultats par page (max 100)
        organization: Filtre par organisation (ex: "ministere")
        tags: Filtre par tags (ex: ["sante", "hopital"])

    Returns:
        Un texte listant les datasets trouves.
    """
    if not query or not query.strip():
        return "Veuillez fournir une requete de recherche."

    # Clamp page_size : < 1 -> default 20, sinon max MAX_PAGE_SIZE
    if page_size < 1:
        page_size = 20
    else:
        page_size = min(page_size, settings.MAX_PAGE_SIZE)
    # Clamp page >= 1
    page = max(1, page)

    cleaned = clean_query(query)
    start = (page - 1) * page_size

    # Construire le fq (filtre CKAN)
    fq_parts: list[str] = []
    if organization:
        fq_parts.append(f"organization:{organization}")
    if tags:
        for tag in tags:
            fq_parts.append(f"tags:{tag}")
    fq = " AND ".join(fq_parts) if fq_parts else None

    async def _search(q: str) -> dict:
        params: dict = {"q": q, "rows": page_size, "start": start}
        if fq:
            params["fq"] = fq
        return await datagov_client.get("/action/package_search", params=params)

    # Phase 1 : requete nettoyee
    data = await _search(cleaned)
    total = data["result"]["count"]
    results = data["result"]["results"]
    used_query = cleaned

    # Phase 2 : fallback sur la requete originale si differente
    if total == 0 and cleaned != query:
        data = await _search(query)
        total = data["result"]["count"]
        results = data["result"]["results"]
        used_query = query

    # Phase 3 : reduction progressive (enlever des mots par la droite)
    if total == 0:
        words = cleaned.split()
        for i in range(len(words) - 1, 0, -1):
            reduced = " ".join(words[:i])
            data = await _search(reduced)
            total = data["result"]["count"]
            results = data["result"]["results"]
            used_query = reduced
            if total > 0:
                break

    if total == 0:
        return f"Aucun resultat trouve pour '{query}'."

    total_pages = math.ceil(total / page_size)

    lines: list[str] = []

    lines.append(f"{total} resultat(s) trouve(s) pour '{query}' :")
    lines.append(f"Page {page}/{total_pages} ({page_size} par page)")
    lines.append("")

    # Indiquer si recherche elargie
    if used_query != query:
        lines.append(f"Recherche elargie : requete reduite a '{used_query}'")
        lines.append("")

    for i, dataset in enumerate(results, start=1):
        titre = dataset.get("title", "Sans titre")
        dataset_id = dataset.get("id", "")
        description = (dataset.get("notes") or "").strip()
        organisation = (dataset.get("organization") or {}).get("title", "Organisation inconnue")
        nb_ressources = dataset.get("num_resources", 0)
        modified = dataset.get("metadata_modified", "")
        dataset_tags = [t.get("name", "") for t in (dataset.get("tags") or [])]

        lines.append(f"{i}. {titre}")
        lines.append(f"   ID : {dataset_id}")
        lines.append(f"   Organisation : {organisation}")
        if description:
            if len(description) > 150:
                description = description[:147] + "..."
            lines.append(f"   Description : {description}")
        if dataset_tags:
            lines.append(f"   Tags : {', '.join(dataset_tags)}")
        if modified:
            lines.append(f"   Modified : {modified}")
        lines.append(f"   ressources: {nb_ressources}")
        lines.append("")

    return "\n".join(lines)
