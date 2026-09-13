"""
Outil MCP A2 : search_dataservices (Famille A - Recherche et Découverte).
Recherche des services de donnees (API) sur data.gov.tn par mots-cles.

Le portail data.gov.tn n'expose pas d'entite "dataservice" distincte :
les services de donnees y sont decrits comme des datasets dont les
ressources utilisent un format oriente API (WFS, WMS, REST, JSON, csv...).
Cet outil interroge donc package_search et met en avant les services.
"""

import math

from config import settings
from helpers.api_client import datagov_client
from helpers.query_cleaner import clean_query

# Formats de ressources considérés comme des "services de donnees" (API).
_SERVICE_FORMATS = {"wfs", "wms", "wcs", "wmts", "rest", "api", "json", "xml", "geojson"}


def _is_service_resource(resource: dict) -> bool:
    fmt = (resource.get("format") or "").lower()
    return fmt in _SERVICE_FORMATS


async def search_dataservices(
    query: str,
    page: int = 1,
    page_size: int = 20,
    organization: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Recherche des services de donnees (API) sur data.gov.tn.

    Args:
        query: Termes de recherche (ex: "météo", "transport").
        page: Numero de page (commence a 1).
        page_size: Nombre de resultats par page (max 100).
        organization: Filtre par organisation (ex: "ministere").
        tags: Filtre par tags (ex: ["climat", "api"]).

    Returns:
        Un texte listant les services de donnees trouves.
    """
    if not query or not query.strip():
        return "Veuillez fournir une requete de recherche."

    if page_size < 1:
        page_size = 20
    else:
        page_size = min(page_size, settings.MAX_PAGE_SIZE)
    page = max(1, page)

    cleaned = clean_query(query)
    start = (page - 1) * page_size

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

    if used_query != query:
        lines.append(f"Recherche elargie : requete reduite a '{used_query}'")
        lines.append("")

    for i, dataset in enumerate(results, start=1):
        titre = dataset.get("title", "Sans titre")
        dataset_id = dataset.get("id", "")
        organisation = (dataset.get("organization") or {}).get("title", "Organisation inconnue")
        description = (dataset.get("notes") or "").strip()
        modified = dataset.get("metadata_modified", "")

        # Ressources orientées service (API)
        services = [res for res in (dataset.get("resources") or []) if _is_service_resource(res)]

        lines.append(f"{i}. {titre}")
        lines.append(f"   ID : {dataset_id}")
        lines.append(f"   Organisation : {organisation}")
        if description:
            if len(description) > 150:
                description = description[:147] + "..."
            lines.append(f"   Description : {description}")

        if services:
            for res in services:
                res_name = res.get("name") or "Service"
                res_fmt = (res.get("format") or "?").upper()
                res_url = res.get("url") or ""
                lines.append(f"   Service : {res_name} [{res_fmt}]")
                if res_url:
                    lines.append(f"      URL : {res_url}")
        else:
            n_res = dataset.get("num_resources", 0)
            lines.append(f"   Ressources : {n_res}")

        if modified:
            lines.append(f"   Modified : {modified}")
        lines.append("")

    return "\n".join(lines)
