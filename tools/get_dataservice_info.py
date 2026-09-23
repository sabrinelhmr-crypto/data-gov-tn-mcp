from helpers.api_client import DataGovError, datagov_client
from helpers.i18n import t

_DOC_FORMATS = ("documentation", "docs", "html", "htm")


def _extras_map(service: dict) -> dict[str, str]:
    extras = service.get("extras") or []
    values: dict[str, str] = {}
    if isinstance(extras, dict):
        for key, value in extras.items():
            values[str(key).lower()] = str(value or "")
    else:
        for item in extras:
            if isinstance(item, dict) and item.get("key"):
                values[str(item.get("key")).lower()] = str(item.get("value") or "")
    return values


def _api_error(data: dict, dataservice_id: str, lang: str) -> str:
    error = data.get("error") or {}
    message = str(
        error.get("message") or error.get("__type") or t("Dataservice introuvable.", lang)
    )
    return f"{t('Erreur', lang)} : {message} (dataservice {dataservice_id})"


def _is_api_resource(resource: dict) -> bool:
    if resource.get("resource_type") == "api":
        return True
    return (resource.get("url") or "").lower().startswith(("http://", "https://")) and (
        resource.get("format") or ""
    ).lower() in ("api", "rest", "json", "xml")


def _is_doc_resource(resource: dict) -> bool:
    if resource.get("resource_type") == "documentation":
        return True
    return (resource.get("format") or "").lower() in _DOC_FORMATS


async def get_dataservice_info(dataservice_id: str, lang: str = "fr") -> str:
    if not dataservice_id or not dataservice_id.strip():
        return t("Veuillez fournir un identifiant de dataservice.", lang)
    try:
        return await _get_dataservice_info(dataservice_id, lang)
    except DataGovError as exc:
        return str(exc)


async def _get_dataservice_info(dataservice_id: str, lang: str) -> str:
    data = await datagov_client.get("/action/package_show", params={"id": dataservice_id})
    if not data.get("success"):
        return _api_error(data, dataservice_id, lang)

    service = data["result"]
    resources = service.get("resources") or []
    api_resources = [r for r in resources if _is_api_resource(r)]
    doc_resources = [r for r in resources if _is_doc_resource(r)]

    endpoint = api_resources[0] if api_resources else (resources[0] if resources else {})
    base_url = service.get("url") or endpoint.get("url") or t("Non renseignée", lang)
    extras = _extras_map(service)

    response_format = (
        endpoint.get("format")
        or extras.get("format")
        or service.get("format")
        or t("Non renseigné", lang)
    ).upper()
    description = (service.get("notes") or "").strip()
    endpoint_url = endpoint.get("url") or t("Non renseigné", lang)
    documentation = None
    if doc_resources:
        first = doc_resources[0]
        documentation = first.get("url") or first.get("name")
    if not documentation:
        documentation = extras.get("documentation") or extras.get("doc_url")

    lines: list[str] = []
    lines.append(service.get("title") or t("Sans titre", lang))
    lines.append("")
    lines.append(f"{t('ID', lang)} : {service.get('id', '')}")
    lines.append(f"{t('Type', lang)} : {service.get('type') or 'dataservice'}")
    if description:
        lines.append(f"{t('Description', lang)} : {description}")
    lines.append(f"{t('URL de base', lang)} : {base_url}")
    lines.append(f"{t('Endpoint principal', lang)} : {endpoint_url}")
    lines.append(f"{t('Format de réponse', lang)} : {response_format}")
    lines.append(f"{t('Documentation', lang)} : {documentation or t('Non renseignée', lang)}")

    return "\n".join(lines)
