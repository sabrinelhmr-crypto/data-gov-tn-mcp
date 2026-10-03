"""Tests unitaires du garde-fou SSRF (helpers/url_guard.py)."""

import ipaddress
import socket

import pytest

from helpers.url_guard import UnsafeURLError, assert_download_url_allowed


def resolver(pairs):
    """Construit un resolver factice : "*" vaut pour tout hote, sinon hote -> adresses."""

    def _resolve(host: str):
        try:
            return [ipaddress.ip_address(a) for a in pairs.get("*", pairs.get(host, []))]
        except ValueError as exc:
            raise AssertionError(f"adresse de test invalide : {exc}") from exc

    return _resolve


def test_accepte_un_hote_public():
    resolve = resolver({"data.gov.tn": ["93.184.216.34"]})
    host = assert_download_url_allowed("https://data.gov.tn/f.csv", resolver=resolve)
    assert host == "data.gov.tn"


def test_normalise_la_casse_de_l_hote():
    resolve = resolver({"catalog.agridata.tn": ["93.184.216.34"]})
    host = assert_download_url_allowed("https://CATALOG.Agridata.TN/f.csv", resolver=resolve)
    assert host == "catalog.agridata.tn"


@pytest.mark.parametrize(
    ("url", "adresse"),
    [
        ("http://127.0.0.1/f.csv", "127.0.0.1"),
        ("http://localhost/f.csv", "127.0.0.1"),
        ("http://10.1.2.3/f.csv", "10.1.2.3"),
        ("http://192.168.1.1/f.csv", "192.168.1.1"),
        ("http://172.16.0.1/f.csv", "172.16.0.1"),
        ("http://169.254.169.254/latest/meta-data/", "169.254.169.254"),
        ("http://[::1]/f.csv", "::1"),
        ("http://[fd00::1]/f.csv", "fd00::1"),
        ("http://[fe80::1]/f.csv", "fe80::1"),
        ("http://0.0.0.0/f.csv", "0.0.0.0"),
        ("http://255.255.255.255/f.csv", "255.255.255.255"),
        ("http://[::ffff:127.0.0.1]/f.csv", "::ffff:127.0.0.1"),
        ("http://224.0.0.1/f.csv", "224.0.0.1"),
    ],
)
def test_refuse_les_adresses_non_publiques(url, adresse):
    resolve = resolver({"*": [adresse]})
    with pytest.raises(UnsafeURLError, match="adresse publique"):
        assert_download_url_allowed(url, resolver=resolve)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://data.gov.tn:70/x",
        "ftp://data.gov.tn/f.csv",
        "data:text/plain,hello",
    ],
)
def test_refuse_les_schemas_interdits(url):
    with pytest.raises(UnsafeURLError, match="Schema d'URL interdit"):
        assert_download_url_allowed(url, resolver=resolver({}))


def test_refuse_les_identifiants_dans_l_url():
    resolve = resolver({"data.gov.tn": ["93.184.216.34"]})
    with pytest.raises(UnsafeURLError, match="identifiants"):
        assert_download_url_allowed("https://u:p@data.gov.tn/f.csv", resolver=resolve)


def test_refuse_une_url_sans_hote():
    with pytest.raises(UnsafeURLError, match="aucun hote"):
        assert_download_url_allowed("https:///f.csv", resolver=resolver({}))


def test_refuse_un_hote_hors_liste_blanche():
    resolve = resolver({"evil.example": ["93.184.216.34"]})
    with pytest.raises(UnsafeURLError, match="Hote non autorise"):
        assert_download_url_allowed(
            "https://evil.example/f.csv",
            allowed_hosts=["*.data.gov.tn", "data.gov.tn"],
            resolver=resolve,
        )


def test_liste_blanche_accepte_le_sous_domaine():
    resolve = resolver({"www.data.gov.tn": ["93.184.216.34"]})
    assert (
        assert_download_url_allowed(
            "https://www.data.gov.tn/f.csv",
            allowed_hosts=["*.data.gov.tn"],
            resolver=resolve,
        )
        == "www.data.gov.tn"
    )


def test_liste_blanche_refuse_le_domaine_mere():
    resolve = resolver({"data.gov.tn": ["93.184.216.34"]})
    with pytest.raises(UnsafeURLError, match="Hote non autorise"):
        assert_download_url_allowed(
            "https://data.gov.tn/f.csv", allowed_hosts=["*.data.gov.tn"], resolver=resolve
        )


def test_liste_blanche_vide_accepte_un_hote_public():
    resolve = resolver({"nimportequoi.example": ["93.184.216.34"]})
    assert (
        assert_download_url_allowed(
            "https://nimportequoi.example/f.csv", allowed_hosts=[], resolver=resolve
        )
        == "nimportequoi.example"
    )


def test_refuse_si_une_adresse_sur_deux_est_privee():
    """Un DNS qui melange public et prive doit etre refuse, pas accepte."""
    resolve = resolver({"mixed.example": ["93.184.216.34", "10.0.0.5"]})
    with pytest.raises(UnsafeURLError, match="adresse publique"):
        assert_download_url_allowed("https://mixed.example/f.csv", resolver=resolve)


def test_hote_introuvable():
    def resolve(host):
        raise socket.gaierror(f"{host}: nom introuvable")

    with pytest.raises(UnsafeURLError, match="Hote introuvable"):
        assert_download_url_allowed("https://absent.example/f.csv", resolver=resolve)


def test_resolveur_par_defaut(monkeypatch):
    import helpers.url_guard as guard

    v6 = ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0)
    infos = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", v6),
    ]
    monkeypatch.setattr(guard.socket, "getaddrinfo", lambda *a, **k: infos)

    assert guard._default_resolver("data.gov.tn") == [
        ipaddress.ip_address("93.184.216.34"),
        ipaddress.ip_address("2606:2800:220:1:248:1893:25c8:1946"),
    ]


def test_resolveur_par_defaut_hote_absent(monkeypatch):
    import helpers.url_guard as guard

    def boom(*args, **kwargs):
        raise socket.gaierror("noms introuvable")

    monkeypatch.setattr(guard.socket, "getaddrinfo", boom)

    with pytest.raises(UnsafeURLError, match="Hote introuvable"):
        guard._default_resolver("absent.example")


@pytest.mark.parametrize(
    ("adresse", "attendu"),
    [
        # IPv4 encapsule en IPv6 : doit etre traite comme l'IPv4 d'origine.
        ("::ffff:127.0.0.1", False),
        ("::ffff:10.0.0.1", False),
        ("::ffff:93.184.216.34", True),
        # 6to4 encapsule un IPv4 prive.
        ("2002:0a00:0001::1", False),
        ("2002:5db8:d822::1", True),
        # Teredo : le client IPv4 est recupere puis evalue.
        ("2001:0:4136:e378:8000:63bf:3fff:fdd2", False),  # client 192.0.2.45
        ("2001:0:4136:e378:0:0:a247:27dd", True),  # client 93.184.216.34
        # site-local (fec0::/10).
        ("fec0::1", False),
    ],
)
def test_adresses_ipv6_encapsulees(adresse, attendu):
    assert guard_is_public(adresse) is attendu


def guard_is_public(adresse: str) -> bool:
    from helpers.url_guard import _is_public

    return _is_public(ipaddress.ip_address(adresse))


def test_motif_de_liste_blanche_vide():
    from helpers.url_guard import _host_matches

    assert _host_matches("data.gov.tn", "") is False
    assert _host_matches("data.gov.tn", "   ") is False
