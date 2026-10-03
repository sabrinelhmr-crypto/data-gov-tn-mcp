"""
Middleware ASGI de limitation de debit (CDC 6.1).

Enveloppe l'application FastMCP et refuse la requete au-dela du quota de
l'IP appelante. Les probes /health sont exemptes : elles viennent de
l'orchestrateur, pas d'un utilisateur.

Chaque reponse porte les en-tetes X-RateLimit-Limit / -Remaining / -Reset,
lisibles par le client sans ouvrir de session, et un refus porte en plus
Retry-After, comme l'exige la RFC 6585 pour un 429.
"""

from collections.abc import Awaitable, Callable, Iterable

from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

from helpers.rate_limit import SlidingWindowRateLimiter, client_key


class RateLimitMiddleware:
    """
    Applique un :class:`SlidingWindowRateLimiter` a chaque requete entrante.

    Args:
        app: Application ASGI suivante (typiquement l'app FastMCP).
        limiter: Compteur a interroger.
        exempt_paths: Chemins ignores (probes de l'orchestrateur).
        trust_proxy: Si vrai, l'IP peut venir de X-Forwarded-For, mais
            seulement si le pair immediat est un proxy de confiance. A
            n'activer que derriere un reverse proxy declare : en acces direct,
            l'en-tete est forgeable et le quota devient inoperant.
        trusted_hosts: Adresses des proxys de confiance. Sans cette liste,
            l'en-tete est ignore meme si ``trust_proxy`` est actif.
        exempt_methods: Methodes HTTP non comptees (OPTIONS ne consomme pas
            de requete metier).
    """

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        limiter: SlidingWindowRateLimiter,
        exempt_paths: Iterable[str] = (),
        trust_proxy: bool = False,
        trusted_hosts: Iterable[str] = (),
        exempt_methods: Iterable[str] = ("OPTIONS",),
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.exempt_paths = frozenset(exempt_paths)
        self.trust_proxy = trust_proxy
        self.trusted_hosts = tuple(trusted_hosts)
        self.exempt_methods = frozenset(exempt_methods)

    def _is_exempt(self, scope: Scope) -> bool:
        if scope.get("method", "GET") in self.exempt_methods:
            return True
        return scope.get("path", "") in self.exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or self._is_exempt(scope):
            await self.app(scope, receive, send)
            return

        key = client_key(scope, trust_proxy=self.trust_proxy, trusted_hosts=self.trusted_hosts)
        decision = self.limiter.hit(key)

        if not decision.allowed:
            retry_after = str(int(decision.retry_after) + 1)
            response = JSONResponse(
                {
                    "error": "Trop de requetes",
                    "message": (
                        f"Quota de {decision.limit} requetes/minute depasse pour cette IP. "
                        f"Reessayez dans {retry_after} s."
                    ),
                    "retry_after": decision.retry_after,
                },
                status_code=429,
                headers={
                    "Retry-After": retry_after,
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": retry_after,
                },
            )
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})["rate_limit"] = decision
        limit_header = str(decision.limit).encode("latin-1")
        remaining_header = str(decision.remaining).encode("latin-1")
        reset_header = str(int(decision.reset_after) + 1).encode("latin-1")
        headers_to_add = [
            (b"x-ratelimit-limit", limit_header),
            (b"x-ratelimit-remaining", remaining_header),
            (b"x-ratelimit-reset", reset_header),
        ]
        sent_headers = False

        async def send_wrapper(message: Message) -> None:
            nonlocal sent_headers
            if message["type"] == "http.response.start" and not sent_headers:
                sent_headers = True
                message.setdefault("headers", []).extend(headers_to_add)
            await send(message)

        await self.app(scope, receive, send_wrapper)


__all__ = ["RateLimitMiddleware"]
