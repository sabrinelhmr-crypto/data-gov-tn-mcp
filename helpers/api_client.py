"""Client HTTP pour API data.gov.tn (CKAN API v3)."""

import httpx

from config import settings


class DatagovAPIError(Exception):
    """Erreur levée quand l'API data.gov.tn ne répond pas correctement."""


class DatagovClient:
    """Client minimal asynchrone pour l'API CKAN de data.gov.tn."""

    def __init__(self) -> None:
        self.base_url = settings.DATAGOV_API_BASE_URL.rstrip("/")
        self._timeout = settings.REQUEST_TIMEOUT
        headers = {"Accept": "application/json"}
        if settings.DATAGOV_API_KEY:
            headers["Authorization"] = settings.DATAGOV_API_KEY
        self._headers = headers

    async def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=self._headers
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise DatagovAPIError(f"Erreur API data.gov.tn ({path}): {exc}") from exc


# Instance unique importable partout : from helpers.api_client import datagov_client
datagov_client = DatagovClient()
