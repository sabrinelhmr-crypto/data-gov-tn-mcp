"""
Client HTTP async pour l'API CKAN de data.gov.tn.

Base de toutes les requetes sortantes du serveur : le point d'entree unique
est ``datagov_client.get(path, params)`` qui renvoie le JSON decode de l'API.
"""

import asyncio
import urllib.parse
from collections.abc import Awaitable, Callable

import httpx

from config import settings
from helpers.url_guard import MAX_REDIRECTS, UnsafeURLError, assert_download_url_allowed

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Statuts HTTP transitoires : la panne est attendue breve (maintenance,
# saturation amont), donc une nouvelle tentative a du sens. Un 4xx definitif
# (400, 404, 403) ne change pas d'une tentative a l'autre : le rejouer
# "./action/package_show" dix fois ne fera pas apparaitre le dataset.
_RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})

# Erreurs reseau pour lesquelles une nouvelle connexion peut reussir.
# ReadTimeout/ConnectError sont transitoires ; un UnsupportedProtocol ne
# l'est pas (l'URL est mauvaise, pas le reseau).
_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


class DatagovAPIError(Exception):
    """Erreur survenue lors d'un appel a l'API data.gov.tn."""


class DownloadTooLargeError(DatagovAPIError):
    """Le telechargement depasse la taille maximale autorisee."""


class UnsafeDownloadURLError(DatagovAPIError):
    """L'URL de la ressource est refusee par le garde-fou SSRF."""


class _TransientStatus(DatagovAPIError):
    """Statut HTTP transitoire rencontre au cours d'un streaming.

    Interne : permet au ``download`` de distinguer « reessayer » d'une erreur
    definitive, sans interferer avec les exceptions exposees aux outils.
    """


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
        max_attempts: int | None = None,
        backoff: float | None = None,
        backoff_max: float | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """
        Args:
            base_url: Racine de l'API CKAN (ex: https://catalog.data.gov.tn/api/3).
            api_key: Cle d'API envoyee en en-tete Authorization, si definie.
            timeout: Delai maximal d'une requete, en secondes.
            verify_ssl: Verification TLS (False uniquement en dev local).
            transport: Transport httpx injectable, pour les tests.
            max_attempts: Nombre total de tentatives, 1 = pas de retry.
            backoff: Delai avant la premiere nouvelle tentative, en secondes.
            backoff_max: Plafond du delai entre deux tentatives.
            sleep: Injection de la fonction d'attente, pour des tests sans
                temps reel. Par defaut : asyncio.sleep.
        """
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
        if max_attempts is None:
            max_attempts = settings.API_MAX_ATTEMPTS
        if backoff is None:
            backoff = settings.API_RETRY_BACKOFF
        if backoff_max is None:
            backoff_max = settings.API_RETRY_BACKOFF_MAX
        self._max_attempts = max(1, max_attempts)
        self._backoff = backoff
        self._backoff_max = backoff_max
        self._sleep = sleep or asyncio.sleep

    def _delay_for(self, attempt: int, retry_after: float | None) -> float:
        """
        Delai avant la tentative ``attempt`` + 1 (backoff exponentiel borne).

        ``Retry-After`` du serveur est prioritaire quand il est exploitable :
        c'est lui qui indique quand la file d'attente amont sera degagee.
        """
        if retry_after is not None and 0 <= retry_after <= self._backoff_max:
            return retry_after
        return min(self._backoff * (2 ** (attempt - 1)), self._backoff_max)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        """Lit l'en-tete Retry-After s'il est en secondes."""
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return float(raw.strip())
        except ValueError:
            return None

    @staticmethod
    def _check_result(path: str, data: dict) -> None:
        """
        Verifie l'invariant d'enveloppe CKAN : ``result`` est present et structure.

        CKAN repond toujours ``{"success": true, "result": ...}``. Si l'enveloppe
        est cassee (``result`` absent, ``null``, ou scalaire), les outils
        liraient au hasard et lèvent une ``KeyError`` brute, qui remonte au
        client MCP comme une erreur interne opaque. On la transforme en
        ``DatagovAPIError``, donc en message lisible pour l'utilisateur final.
        """
        if "result" not in data:
            raise DatagovAPIError(f"Reponse inattendue de l'API sur {path} : champ 'result' absent")
        result = data["result"]
        if result is None or not isinstance(result, dict | list):
            raise DatagovAPIError(
                f"Reponse inattendue de l'API sur {path} : 'result' n'est pas un objet"
            )

    async def get(self, path: str, params: dict | None = None) -> dict:
        """
        Execute un GET sur l'API CKAN et renvoie le payload JSON.

        Les erreurs transitoires (timeout, panne reseau, 429/502/503/504) sont
        reessayees avec un backoff exponentiel borne, pour que le portail soit
        momentanement indisponible ne se traduise pas par une erreur remise
        au client.

        Args:
            path: Chemin de l'action CKAN (ex: "/action/package_search").
            params: Parametres de requete (q, rows, start, fq, ...).

        Returns:
            Le dictionnaire JSON de l'API (cle "result" incluse).

        Raises:
            DatagovAPIError: Erreur reseau persistante, statut HTTP != 200
                apres epuisement des tentatives, reponse non-JSON ou champ
                CKAN ``success`` a False.
        """
        last_error = "cause inconnue"

        for attempt in range(1, self._max_attempts + 1):
            is_last = attempt == self._max_attempts

            try:
                response = await self._client.get(path, params=params)
            except _RETRYABLE_EXCEPTIONS as exc:
                # httpx laisse parfois une exception sans texte : on nomme alors
                # la classe, sinon le message fini sur ":  apres 3 tentatives".
                cause = str(exc) or type(exc).__name__
                last_error = f"Erreur reseau vers data.gov.tn ({path}) : {cause}"
                if is_last:
                    break
                await self._sleep(self._delay_for(attempt, None))
                continue
            except httpx.HTTPError as exc:
                raise DatagovAPIError(f"Erreur reseau vers data.gov.tn ({path}) : {exc}") from exc

            if response.status_code in _RETRYABLE_STATUSES:
                last_error = f"HTTP {response.status_code} sur {path}"
                if is_last:
                    break
                retry_after = self._retry_after_seconds(response)
                await self._sleep(self._delay_for(attempt, retry_after))
                continue

            if response.status_code != 200:
                raise DatagovAPIError(f"HTTP {response.status_code} sur {path}")

            try:
                data = response.json()
            except ValueError as exc:
                raise DatagovAPIError(f"Reponse non-JSON de l'API sur {path}") from exc

            if data.get("success") is False:
                message = (data.get("error") or {}).get("message", "Erreur CKAN inconnue")
                raise DatagovAPIError(f"Erreur CKAN sur {path} : {message}")

            self._check_result(path, data)

            return data

        raise DatagovAPIError(f"{last_error} apres {self._max_attempts} tentatives")

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

            # Les erreurs transitoires sont reessayees ; un depassement de taille
            # ne l'est jamais (relire un fichier rejete pour sa taille serait
            # pure perte de bande passante).
            for attempt in range(1, self._max_attempts + 1):
                is_last = attempt == self._max_attempts
                try:
                    content, redirect = await self._download_once(current, max_bytes)
                except _RETRYABLE_EXCEPTIONS as exc:
                    cause = str(exc) or type(exc).__name__
                    if is_last:
                        raise DatagovAPIError(
                            f"Erreur reseau lors du telechargement ({_safe_url(current)}) : {cause}"
                        ) from exc
                    await self._sleep(self._delay_for(attempt, None))
                    continue
                except _TransientStatus as exc:
                    if is_last:
                        raise DatagovAPIError(
                            f"{exc} lors du telechargement de {_safe_url(current)}"
                        ) from exc
                    await self._sleep(self._delay_for(attempt, None))
                    continue

                if redirect is not None:
                    current = urllib.parse.urljoin(current, redirect)
                    break
                return content

        raise DatagovAPIError(f"Trop de redirections ({MAX_REDIRECTS}) depuis {_safe_url(url)}")

    async def _download_once(self, url: str, max_bytes: int) -> tuple[bytes, str | None]:
        """
        Une tentative de telechargement.

        Returns:
            ``(contenu, None)`` si le fichier est telecharge, ou
            ``(b"", destination)`` si la reponse est une redirection.
        """
        try:
            async with self._client.stream("GET", url, follow_redirects=False) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise DatagovAPIError(
                            f"Redirection sans en-tete Location depuis {_safe_url(url)}"
                        )
                    return b"", location

                if response.status_code != 200:
                    if response.status_code in _RETRYABLE_STATUSES:
                        raise _TransientStatus(f"HTTP {response.status_code}")
                    raise DatagovAPIError(
                        f"HTTP {response.status_code} lors du telechargement de {_safe_url(url)}"
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
                return b"".join(chunks), None
        except httpx.HTTPError as exc:
            raise DatagovAPIError(
                f"Erreur reseau lors du telechargement ({_safe_url(url)}) : {exc}"
            ) from exc

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
