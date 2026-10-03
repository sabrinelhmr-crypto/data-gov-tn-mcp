"""
Limitation de debit par IP (CDC 6.1 : 100 requetes/minute/IP).

Le portail est public et sans authentification (Decret 2021-3, art. 9) :
ce quota est donc le seul garde-fou disponible contre l'epuisement du service
par un seul appelant. Il est applique ici, dans l'application, et non au
reverse proxy, pour etre verifiable par les tests et par Locust.

Modele : fenetre glissante. Chaque IP conserve l'historique de ses horodatages
sur la fenetre ; la limite vaut ``limit + burst`` requetes. La fenetre glissante
evite le piege de la fenetre fixe, ou deux rafales espacees de quelques
millisecondes de part et d'autre d'une bascule sont toutes deux acceptees.

L'IP cliente provient du socket, sauf si le reverse proxy est explicitement
declare de confiance : sans cela, un en-tete X-Forwarded-For forgee suffirait
a contourner le quota.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

Clock = Callable[[], float]


@dataclass(frozen=True)
class Decision:
    """Verdict du limiteur pour une requete donnee."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_after: float


class SlidingWindowRateLimiter:
    """
    Compteur de requetes par cle, sur une fenetre glissante.

    Args:
        limit: Requetes autorisees par fenetre, horsTolerance.
        window: Longueur de la fenetre, en secondes (60 = une minute).
        burst: Requetes tolerees au-dela de ``limit`` avant refus.
        clock: Horloge injectable, pour des tests sans temps reel.
        max_keys: Nombre maximum de cles suivies ; au-dela, la cle la moins
            recently utilisee est oubliee. Borne la memoire quand les IP
            sont reellement variees.
    """

    def __init__(
        self,
        limit: int,
        window: float = 60.0,
        burst: int = 0,
        clock: Clock | None = None,
        max_keys: int = 10_000,
    ) -> None:
        if limit < 0:
            raise ValueError("limit doit etre positif ou nul.")
        if window <= 0:
            raise ValueError("window doit etre strictement positive.")
        if burst < 0:
            raise ValueError("burst doit etre positif ou nul.")
        self.limit = limit
        self.window = window
        self.burst = burst
        self._clock = clock or time.monotonic
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_seen: dict[str, float] = {}

    @property
    def quota(self) -> int:
        """Budget total d'une fenetre : la limite plus la tolerance."""
        return self.limit + self.burst

    def _evict_if_needed(self) -> None:
        """Oublie les cles les moins recemment vues quand le dict deborde."""
        if len(self._hits) <= self._max_keys:
            return
        cutoff = self._clock()
        expired = [key for key, seen in self._last_seen.items() if cutoff - seen > self.window]
        for key in expired:
            self._forget(key)
        if len(self._hits) <= self._max_keys:
            return
        surplus = len(self._hits) - self._max_keys
        for key in sorted(self._last_seen, key=self._last_seen.get)[:surplus]:  # type: ignore[arg-type]
            self._forget(key)

    def _forget(self, key: str) -> None:
        self._hits.pop(key, None)
        self._last_seen.pop(key, None)

    def hit(self, key: str) -> Decision:
        """
        Enregistre une requete pour ``key`` et renvoie le verdict.

        Une requete refusee n'est pas comptee : un client qui insiste ne doit
        pas pouvoir allonger sa propre fenetre.
        """
        now = self._clock()
        self._last_seen[key] = now

        hits = self._hits[key]
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self.quota:
            oldest = hits[0]
            retry_after = self.window - (now - oldest)
            return Decision(
                allowed=False,
                limit=self.limit,
                remaining=0,
                retry_after=round(max(retry_after, 0.0), 3),
                reset_after=round(max(retry_after, 0.0), 3),
            )

        hits.append(now)
        self._evict_if_needed()

        remaining = max(self.quota - len(hits), 0)
        reset_after = round(max(self.window - (now - hits[0]), 0.0), 3)
        return Decision(
            allowed=True,
            limit=self.limit,
            remaining=remaining,
            retry_after=0.0,
            reset_after=reset_after,
        )

    def peek(self, key: str) -> Decision:
        """Etat du quota sans consommer de requete (pour l'en-tete X-RateLimit)."""
        now = self._clock()
        hits = self._hits.get(key)
        cutoff = now - self.window
        active = [t for t in (hits or ()) if t > cutoff]
        oldest = active[0] if active else now
        return Decision(
            allowed=len(active) < self.quota,
            limit=self.limit,
            remaining=max(self.quota - len(active), 0),
            retry_after=0.0,
            reset_after=round(max(self.window - (now - oldest), 0.0), 3),
        )

    def reset(self, key: str | None = None) -> None:
        """Oublie une cle, ou toutes les cles si ``key`` est absent."""
        if key is None:
            self._hits.clear()
            self._last_seen.clear()
        else:
            self._forget(key)

    def tracked_keys(self) -> Iterable[str]:
        """Cles actuellement suivies (diagnostic et tests)."""
        return tuple(self._hits)


def _host_allowed(peer: str, patterns: Iterable[str]) -> bool:
    """Le pair immediate correspond-il a un proxy declare de confiance ?"""
    for pattern in patterns:
        if pattern == "*" or pattern == peer:
            return True
        if pattern.startswith("*.") and peer.endswith(pattern[1:]):
            return True
        if pattern.startswith(".") and peer.endswith(pattern):
            return True
    return False


def client_key(
    scope: dict,
    trust_proxy: bool = False,
    trusted_hosts: Iterable[str] = (),
) -> str:
    """
    Identifiant de l'appelant pour un scope ASGI.

    Par defaut, l'adresse du socket : seule l'application sait qui l'a
    appelee. ``X-Forwarded-For`` n'est lu que si ``trust_proxy`` est actif
    **et** que le pair immediate est un proxy de confiance. Sans cette double
    condition, un ``X-Forwarded-For`` forgee suffirait a obtenir un quota
    neuf a chaque requete.

    Si la confiance est declaree sans liste de proxys, on retombe sur le pair :
    un garde-fou de securite doit echouer de facon fermee, pas ouverte.
    """
    headers = {
        k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", ())
    }
    peer = ""
    client = scope.get("client")
    if client:
        peer = str(client[0])

    if trust_proxy and _host_allowed(peer, trusted_hosts):
        forwarded = headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or peer or "unknown"
        real_ip = headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip

    return peer or "unknown"
