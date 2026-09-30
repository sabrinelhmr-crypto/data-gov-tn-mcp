"""
Garde-fou SSRF pour les telechargements de l'outil C2.

L'URL d'une ressource vient des metadonnees du portail : c'est une source
semi-siegee, car un producteur de donnees peut y inscrire une adresse qu'il
controle. Sans verification, le serveur irait chercher cette adresse pour
lui, ce qui lui permet d'atteindre le reseau interne, les endpoints de
metadonnees du cloud ou un service interne non expose.

La verification porte sur trois points :
- le schema (http/https uniquement, pas file:// ni gopher://) ;
- l'hote, si une liste blanche est configuree ;
- les adresses IP resolues, qui ne doivent pas etre privees, loopback,
  link-local, multicast, reservees ou non specifiees.
"""

import ipaddress
import socket
import urllib.parse
from collections.abc import Callable, Sequence

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Nombre maximum de redirections suivies manuellement. Chaque saut est
# revalide, donc une boucle ne peut pas eluder le garde-fou.
MAX_REDIRECTS = 3

Resolver = Callable[[str], list[ipaddress.IPv4Address | ipaddress.IPv6Address]]


class UnsafeURLError(ValueError):
    """URL refusee : schema interdit, hote hors liste blanche ou IP non publique."""


def _default_resolver(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resout un hote en adresses IP, sans cache ni service externe."""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Hote introuvable : {host}") from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def _is_public(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Vrai si l'adresse est routable sur Internet public."""
    if isinstance(addr, ipaddress.IPv6Address):
        mapped = addr.ipv4_mapped
        if mapped is not None:
            return _is_public(mapped)
        if addr.sixtofour is not None:
            return _is_public(addr.sixtofour)
        if addr.teredo is not None:
            return _is_public(addr.teredo[1])
        if addr.is_site_local:
            return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _host_matches(host: str, pattern: str) -> bool:
    pattern = pattern.strip().lower()
    if not pattern:
        return False
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return host.endswith(suffix) and host != suffix[1:]
    return host == pattern


def assert_download_url_allowed(
    url: str,
    *,
    allowed_hosts: Sequence[str] = (),
    resolver: Resolver | None = None,
) -> str:
    """
    Verifie qu'une URL de telechargement ne peut pas viser le reseau interne.

    Args:
        url: URL absolue a verifier.
        allowed_hosts: Hotes autorises. Une entree peut commencer par ``*.``
            pour couvrir un sous-domaine. Vide = tout hote public est accepte.
        resolver: Resolution DNS injectable, pour les tests.

    Returns:
        L'hote verifie, en minuscules.

    Raises:
        UnsafeURLError: URL mal formee, schema interdit, hote hors liste
            blanche, ou adresse resolue non publique.
    """
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"Schema d'URL interdit : '{parsed.scheme or 'vide'}'. "
            "Seuls http et https sont acceptes."
        )

    if parsed.username or parsed.password:
        raise UnsafeURLError("URL refusee : les identifiants dans l'URL sont interdits.")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise UnsafeURLError("URL refusee : aucun hote.")

    patterns = [p for p in allowed_hosts if p and p.strip()]
    if patterns and not any(_host_matches(host, p) for p in patterns):
        raise UnsafeURLError(f"Hote non autorise pour le telechargement : '{host}'.")

    resolve = resolver or _default_resolver
    try:
        addresses = resolve(host)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Hote introuvable : {host}") from exc

    for addr in addresses:
        if not _is_public(addr):
            raise UnsafeURLError(f"Hote non resolu vers une adresse publique : '{host}' ({addr}).")

    return host
