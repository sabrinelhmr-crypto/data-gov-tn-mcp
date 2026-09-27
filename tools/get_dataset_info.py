
"""
Outil MCP B1 : get_dataset_info (Famille B - Inspection et Metadonnees).
Affiche les metadonnees detaillees d'un dataset via package_show.
"""

from helpers.api_client import DatagovAPIError, datagov_client

_MAX_DESC_LEN = 300

# Champs cles retenus pour le calcul de la qualite des metadonnees (CDC B1).
_QUALITY_FIELDS = 10

# Cles CKAN (extras) pour la frequence de mise a jour.
_FREQUENCY_KEYS = {"frequency", "frequence", "update_frequency", "frequence_de_mise_a_jour"}


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _metadata_quality(d: dict) -> tuple[int, str]:
    """Calcule un score de qualite : champs presents parmi les champs cles."""
    checks = [
        bool(d.get("title")),
        bool(d.get("notes")),
        bool((d.get("organization") or {}).get("title")),
        bool(d.get("license_title")),
        bool(d.get("tags")),
        bool(d.get("groups")),
        bool(d.get("author") or d.get("maintainer")),
        bool(d.get("metadata_created")),
        bool(d.get("metadata_modified")),
        bool(d.get("resources")),
    ]
    score = sum(checks)
    pct = round(score * 100 / _QUALITY_FIELDS)
    return score, f"{score}/{_QUALITY_FIELDS} champs remplis ({pct}%)"


def _update_frequency(d: dict) -> str | None:
    """Recupere la frequence de mise a jour depuis les extras CKAN."""
    for extra in d.get("extras") or []:
        if not isinstance(extra, dict):
            continue
        key = (extra.get("key") or "").strip().lower()
        value = (extra.get("value") or "").strip()
        if key in _FREQUENCY_KEYS and value:
            return value
    return None


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

    frequency = _update_frequency(d)
    if frequency:
        lines.append(f"Frequence de mise a jour : {frequency}")

    _, quality = _metadata_quality(d)
    lines.append(f"Qualite des metadonnees : {quality}")

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
=======
from helpers.api_client import DataGovError, datagov_client
from helpers.i18n import t

_FREQUENCY_EXTRAS = (
    "frequency",
    "update_frequency",
    "freq",
    "frequence",
    "fréquence",
)


def _extras_map(package: dict) -> dict[str, str]:
    extras = package.get("extras") or []
    values: dict[str, str] = {}
    if isinstance(extras, dict):
        for key, value in extras.items():
            values[str(key).lower()] = str(value or "")
    else:
        for item in extras:
            if isinstance(item, dict) and item.get("key"):
                values[str(item.get("key")).lower()] = str(item.get("value") or "")
    return values


def _extract_frequency(package: dict) -> str | None:
    extras = _extras_map(package)
    for key in _FREQUENCY_EXTRAS:
        if extras.get(key, "").strip():
            return extras[key].strip()
    return None


def _metadata_quality(package: dict) -> tuple[int, list[str]]:
    checks: list[tuple[str, bool]] = [
        ("titre", bool(package.get("title"))),
        ("description", bool((package.get("notes") or "").strip())),
        ("organisation", bool(package.get("organization"))),
        ("licence", bool(package.get("license_title") or package.get("license_id"))),
        ("date de création", bool(package.get("metadata_created"))),
        ("date de modification", bool(package.get("metadata_modified"))),
        ("tags", bool(package.get("tags"))),
        ("fréquence de mise à jour", _extract_frequency(package) is not None),
    ]
    present = sum(ok for _, ok in checks)
    missing = [label for label, ok in checks if not ok]
    return round(present / len(checks) * 100), missing


def _api_error(data: dict, lang: str) -> str:
    error = data.get("error") or {}
    message = str(error.get("message") or error.get("__type") or t("Dataset introuvable.", lang))
    return f"{t('Erreur', lang)} : {message}"


async def get_dataset_info(dataset_id: str, lang: str = "fr") -> str:
    if not dataset_id or not dataset_id.strip():
        return t("Veuillez fournir un identifiant de dataset.", lang)
    try:
        return await _get_dataset_info(dataset_id, lang)
    except DataGovError as exc:
        return str(exc)


async def _get_dataset_info(dataset_id: str, lang: str) -> str:
    data = await datagov_client.get("/action/package_show", params={"id": dataset_id})
    if not data.get("success"):
        return _api_error(data, lang)

    package = data["result"]
    organisation = (package.get("organization") or {}).get("title") or t(
        "Organisation inconnue", lang
    )
    description = (package.get("notes") or "").strip()
    dataset_tags = [
        item.get("name", "") if isinstance(item, dict) else str(item)
        for item in (package.get("tags") or [])
    ]
    licence = package.get("license_title") or package.get("license_id") or t("Non renseignée", lang)
    created = package.get("metadata_created")
    modified = package.get("metadata_modified")
    num_resources = package.get("num_resources", len(package.get("resources") or []))
    score, missing = _metadata_quality(package)

    lines: list[str] = []
    lines.append(package.get("title") or t("Sans titre", lang))
    lines.append("")
    lines.append(f"{t('ID', lang)} : {package.get('id', '')}")
    lines.append(f"{t('Organisation', lang)} : {organisation}")
    if description:
        lines.append(f"{t('Description', lang)} : {description}")
    if dataset_tags:
        lines.append(f"{t('Tags', lang)} : {', '.join(dataset_tags)}")
    lines.append(f"{t('Licence', lang)} : {licence}")
    frequency = _extract_frequency(package) or t("Non renseignée", lang)
    lines.append(f"{t('Fréquence de mise à jour', lang)} : {frequency}")
    lines.append(f"{t('Créé le', lang)} : {created or t('Non renseignée', lang)}")
    lines.append(f"{t('Dernière modification', lang)} : {modified or t('Non renseignée', lang)}")
    lines.append(f"{t('Nombre de ressources', lang)} : {num_resources}")
    lines.append(f"{t('Qualité des métadonnées', lang)} : {score}%")
    if missing:
        translated = ", ".join(t(name, lang) for name in missing)
        lines.append(f"   {t('Champs manquants', lang)} : {translated}")


    return "\n".join(lines)
