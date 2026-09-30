"""
Outil MCP C3 : get_metrics (Famille C - Analyse de Donnees).
Indicateurs d'usage d'un dataset ou du portail (disponible en prod uniquement).
"""

from config import settings
from helpers.api_client import DatagovAPIError, datagov_client

# Periodes d'analyse acceptees (CDC C3).
_PERIODS = {"7d", "30d", "90d", "1y"}

_DEFAULT_PERIOD = "30d"


async def _dataset_metrics(dataset_id: str) -> str:
    """
    Indicateurs d'usage pour un dataset : telechargements (par ressource et total).
    La plateforme data.gov.tn n'expose pas de vues/reutilisations/tendance.
    """
    try:
        data = await datagov_client.get("/action/package_show", params={"id": dataset_id})
    except DatagovAPIError as exc:
        return f"Dataset introuvable pour '{dataset_id}' : {exc}"

    package = data["result"]
    resources = package.get("resources") or []

    lines: list[str] = []
    lines.append(f"Dataset : {package.get('title', 'Sans titre')}")
    lines.append(f"ID : {package.get('id', '')}")
    lines.append("")

    if not resources:
        lines.append("Ce dataset ne contient aucune ressource.")
        return "\n".join(lines)

    total = 0
    lines.append(f"Telechargements par ressource ({len(resources)}) :")
    for i, res in enumerate(resources, start=1):
        res_name = (res.get("name") or "Sans nom").strip()
        if len(res_name) > 80:
            res_name = res_name[:77] + "..."
        downloads = res.get("downloads_count")
        total += downloads if isinstance(downloads, int) else 0
        count = (
            f"{downloads:,}".replace(",", " ")
            if isinstance(downloads, int | float)
            else "indisponible"
        )
        lines.append(f"  {i}. {res_name} : {count} telechargement(s)")
    lines.append("")
    lines.append(f"Total des telechargements : {total:,}".replace(",", " "))
    lines.append("Vues : indisponible via l'API")
    lines.append("Reutilisations : indisponible via l'API")
    lines.append("Tendance : indisponible via l'API (pas d'historique)")

    return "\n".join(lines)


async def _portal_metrics() -> str:
    """
    Indicateurs globaux du portail : nombre de datasets, d'organisations et de themes.
    Les statistiques d'usage (telechargements) globales ne sont pas exposees.
    """
    try:
        search = await datagov_client.get("/action/package_search", params={"rows": 0})
        organizations = await datagov_client.get("/action/organization_list")
        themes = await datagov_client.get("/action/group_list")
    except DatagovAPIError as exc:
        return f"Impossible de recuperer les indicateurs du portail : {exc}"

    datasets = (search.get("result") or {}).get("count", 0)
    organizations = organizations.get("result") or []
    groups = themes.get("result") or []

    lines: list[str] = []
    lines.append(f"Datasets disponibles : {datasets:,}".replace(",", " "))
    lines.append(f"Organisations : {len(organizations):,}".replace(",", " "))
    lines.append(f"Themes (groupes) : {len(groups):,}".replace(",", " "))
    lines.append("")
    lines.append("Telechargements globaux : indisponible via l'API")
    lines.append("Vues / reutilisations : indisponible via l'API")

    return "\n".join(lines)


async def get_metrics(dataset_id: str | None = None, period: str = _DEFAULT_PERIOD) -> str:
    """
    Indicateurs d'usage d'un dataset ou du portail data.gov.tn.

    Args:
        dataset_id: Identifiant CKAN du dataset (si vide, indicateurs globaux).
        period: Periode d'analyse parmi 7d, 30d, 90d, 1y (defaut 30d).

    Returns:
        Un texte structure listant les indicateurs disponibles.
    """
    if settings.DATAGOV_API_ENV != "prod":
        return (
            "Indicateurs d'usage disponibles uniquement en environnement production "
            "(reglez DATAGOV_API_ENV=prod)."
        )

    period = (period or _DEFAULT_PERIOD).strip().lower()
    if period not in _PERIODS:
        periods = ", ".join(sorted(_PERIODS))
        return f"Periode '{period}' non valide (valeurs acceptees : {periods})."

    lines: list[str] = []
    lines.append("Indicateurs d'usage")
    lines.append(f"Periode : {period}")
    lines.append("")

    if dataset_id and dataset_id.strip():
        lines.append(await _dataset_metrics(dataset_id.strip()))
    else:
        lines.append(await _portal_metrics())

    return "\n".join(lines)
