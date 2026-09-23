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
