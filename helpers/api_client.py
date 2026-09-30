"""
Client HTTP async pour l'API CKAN de data.gov.tn.

Base de toutes les requetes sortantes du serveur : le point d'entree unique
est ``datagov_client.get(path, params)`` qui renvoie le JSON decode de l'API.
"""

import urllib.parse

import httpx

from config import settings
from helpers.url_guard import MAX_REDIRECTS, UnsafeURLError, assert_download_url_allowed

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class DatagovAPIError(Exception):
    """Erreur survenue lors d'un appel a l'API data.gov.tn."""


class DownloadTooLargeError(DatagovAPIError):
    """Le telechargement depasse la taille maximale autorisee."""


class UnsafeDownloadURLError(DatagovAPIError):
    """L'URL de la ressource est refusee par le garde-fou SSRF."""


def _safe_url(url: str) -> str:
    """URL sans identifiants, pour les messages d'erreur et les logs."""
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))


class DatagovClient:
    """Client minimaliste pour l'API CKAN (v2 actions/...)."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {"Authorization": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            verify=verify_ssl,
            transport=transport,
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

    async def download(
        self,
        url: str,
        *,
        max_bytes: int,
        allowed_hosts: list[str] | None = None,
    ) -> bytes:
        """
        Telecharge une ressource (fichier) en bornant la taille recue.

        Le contenu est lu par blocs et la lecture s'interrompt des que
        ``max_bytes`` est depasse : la limite est donc appliquee pendant le
        telechargement, et non apres coup. Chaque URL de redirection est
        revalidee par le garde-fou SSRF.

        Args:
            url: URL absolue du fichier (ex: URL de telechargement d'une ressource).
            max_bytes: Taille maximale acceptable, en octets.
            allowed_hosts: Hotes autorises ; vide = tout hote public.

        Returns:
            Les octets bruts du fichier.

        Raises:
            DownloadTooLargeError: Le fichier depasse ``max_bytes``.
            UnsafeDownloadURLError: URL refusee par le garde-fou SSRF.
            DatagovAPIError: Erreur reseau, statut HTTP != 200, ou trop de
                redirections.
        """
        current = url
        hosts = allowed_hosts if allowed_hosts is not None else settings.download_allowed_hosts_list

        for _hop in range(MAX_REDIRECTS + 1):
            try:
                assert_download_url_allowed(current, allowed_hosts=hosts)
            except UnsafeURLError as exc:
                raise UnsafeDownloadURLError(str(exc)) from exc

            try:
                async with self._client.stream("GET", current, follow_redirects=False) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise DatagovAPIError(
                                f"Redirection sans en-tete Location depuis {_safe_url(current)}"
                            )
                        current = urllib.parse.urljoin(current, location)
                        continue

                    if response.status_code != 200:
                        raise DatagovAPIError(
                            f"HTTP {response.status_code} lors du telechargement "
                            f"de {_safe_url(current)}"
                        )

                    declared = response.headers.get("content-length")
                    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                        raise DownloadTooLargeError(
                            f"Fichier trop volumineux : {declared} octets declares "
                            f"pour un maximum de {max_bytes}."
                        )

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise DownloadTooLargeError(
                                f"Fichier trop volumineux : plus de {max_bytes} octets recus."
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.HTTPError as exc:
                raise DatagovAPIError(
                    f"Erreur reseau lors du telechargement ({_safe_url(current)}) : {exc}"
                ) from exc

        raise DatagovAPIError(f"Trop de redirections ({MAX_REDIRECTS}) depuis {_safe_url(url)}")

    async def aclose(self) -> None:
        """Ferme proprement la connexion HTTP."""
        await self._client.aclose()


# Alias utilise par les outils Famille B (branche famille-b-inspection).
DataGovError = DatagovAPIError
# Instance unique, utilisable partout : from helpers.api_client import datagov_client
datagov_client = DatagovClient(
    base_url=settings.DATAGOV_API_BASE_URL,
    api_key=settings.DATAGOV_API_KEY,
    timeout=settings.REQUEST_TIMEOUT,
    verify_ssl=settings.DATAGOV_API_VERIFY_SSL,
)
