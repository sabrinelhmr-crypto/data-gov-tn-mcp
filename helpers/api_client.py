"""
Client HTTP async pour l'API CKAN de data.gov.tn.

Base de toutes les requetes sortantes du serveur : le point d'entree unique
est ``datagov_client.get(path, params)`` qui renvoie le JSON decode de l'API.
"""

import httpx

from config import settings


class DatagovAPIError(Exception):
    """Erreur survenue lors d'un appel a l'API data.gov.tn."""


class DatagovClient:
    """Client minimaliste pour l'API CKAN (v2 actions/...)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
        verify_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {"Authorization": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            verify=verify_ssl,
        )

    async def get(self, path: str, params: dict | None = None) -> dict:
        """
        Execute un GET sur l'API CKAN et renvoie le payload JSON.

        Args:
            path: Chemin de l'action CKAN (ex: "/action/package_search").
            params: Parametres de requete (q, rows, start, fq, ...).

        Returns:
            Le dictionnaire JSON de l'API (cle "result" incluse).

        Raises:
            DatagovAPIError: Erreur reseau, statut HTTP != 200, reponse
                non-JSON ou champ CKAN ``success`` a False.
        """
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise DatagovAPIError(f"Erreur reseau vers data.gov.tn ({path}) : {exc}") from exc

        if response.status_code != 200:
            raise DatagovAPIError(f"HTTP {response.status_code} sur {path}")

        try:
            data = response.json()
        except ValueError as exc:
            raise DatagovAPIError(f"Reponse non-JSON de l'API sur {path}") from exc

        if data.get("success") is False:
            message = (data.get("error") or {}).get("message", "Erreur CKAN inconnue")
            raise DatagovAPIError(f"Erreur CKAN sur {path} : {message}")

        return data

    async def aclose(self) -> None:
        """Ferme proprement la connexion HTTP."""
        await self._client.aclose()


# Instance unique, utilisable partout : from helpers.api_client import datagov_client
datagov_client = DatagovClient(
    base_url=settings.DATAGOV_API_BASE_URL,
    api_key=settings.DATAGOV_API_KEY,
    timeout=settings.REQUEST_TIMEOUT,
    verify_ssl=settings.DATAGOV_API_VERIFY_SSL,
)
