import json

import httpx

from config import settings
from helpers.api_client import DataGovError, datagov_client
from helpers.i18n import t

_MAX_SPEC_BYTES = 2 * 1024 * 1024

_OPENAPI_FORMATS = {
    "openapi",
    "openapi3",
    "openapi30",
    "openapi31",
    "swagger",
    "api-specification",
    "specification",
}
_SPEC_KEYWORDS = ("openapi", "swagger", "specification", "spécification", "spec")
_SPEC_EXTRAS = ("openapi_url", "openapi_spec", "spec_url", "specs_url", "swagger_url")


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


def _looks_like_spec_url(value: str) -> bool:
    low = value.lower()
    if any(k in low for k in _SPEC_KEYWORDS):
        return True
    return low.rstrip("/").endswith(
        ("openapi.json", "openapi.yaml", "openapi.yml", "swagger.json", "swagger.yaml")
    )


def _find_spec_url(service: dict) -> tuple[str, str] | None:
    for resource in service.get("resources") or []:
        fmt = (resource.get("format") or "").lower()
        name = resource.get("name") or ""
        url = resource.get("url") or ""
        if fmt in _OPENAPI_FORMATS or _looks_like_spec_url(f"{name} {url}"):
            return url, "source_resource"
    extras = _extras_map(service)
    for key in _SPEC_EXTRAS:
        value = extras.get(key, "").strip()
        if value and value.startswith(("http://", "https://")):
            return value, "source_extra"
    base_url = service.get("url")
    if base_url:
        return f"{base_url.rstrip('/')}/openapi.json", "source_base"
    return None


def _api_error(data: dict, dataservice_id: str, lang: str) -> str:
    error = data.get("error") or {}
    message = str(
        error.get("message") or error.get("__type") or t("Dataservice introuvable.", lang)
    )
    return f"{t('Erreur', lang)} : {message} (dataservice {dataservice_id})"


async def _fetch_spec(url: str) -> str | None:
    max_bytes = min(_MAX_SPEC_BYTES, settings.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024)
    chunks: list[bytes] = []
    total = 0
    async with (
        httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT, verify=settings.DATAGOV_API_VERIFY_SSL
        ) as client,
        client.stream("GET", url, follow_redirects=True) as response,
    ):
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                return None
            chunks.append(chunk)
    text = b"".join(chunks).decode("utf-8", errors="replace")
    return _format_spec(text)


def _format_spec(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.dumps(json.loads(stripped), indent=2, ensure_ascii=False)
        except ValueError:
            return text
    return text


async def get_dataservice_openapi_spec(dataservice_id: str, lang: str = "fr") -> str:
    if not dataservice_id or not dataservice_id.strip():
        return t("Veuillez fournir un identifiant de dataservice.", lang)
    try:
        return await _get_dataservice_openapi_spec(dataservice_id, lang)
    except DataGovError as exc:
        return str(exc)


async def _get_dataservice_openapi_spec(dataservice_id: str, lang: str) -> str:
    data = await datagov_client.get("/action/package_show", params={"id": dataservice_id})
    if not data.get("success"):
        return _api_error(data, dataservice_id, lang)

    service = data["result"]
    title = service.get("title") or t("Sans titre", lang)
    found = _find_spec_url(service)
    if not found:
        return t("spec_not_found", lang).format(title=title)
    url, source_key = found
    source = t(source_key, lang)

    try:
        spec = await _fetch_spec(url)
    except httpx.HTTPError as exc:
        return t("spec_fetch_error", lang).format(title=title, url=url, error=exc)
    if spec is None:
        return t("spec_too_large", lang).format(title=title)

    return t("spec_header", lang).format(title=title, source=source) + f"\n\n{spec}"
