"""Tests du durcissement du transport HTTP (main.py)."""

import importlib

import httpx
import pytest

main_mod = importlib.import_module("main")


def test_produit_l_origines_en_local(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "local")
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "*")
    monkeypatch.setattr(main_mod.settings, "CORS_ENABLED", True)

    assert main_mod._origin_allowlist() == ["*"]


def test_refuse_le_joker_en_production(monkeypatch):
    """Un endpoint MCP sans authentification ne doit pas accepter '*' en prod."""
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "prod")
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        main_mod._origin_allowlist()


def test_accepte_une_liste_explicite_en_production(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "prod")
    monkeypatch.setattr(
        main_mod.settings, "ALLOWED_ORIGINS", "https://mcp.data.gov.tn,https://x.tn"
    )
    monkeypatch.setattr(main_mod.settings, "CORS_ENABLED", True)

    assert main_mod._origin_allowlist() == ["https://mcp.data.gov.tn", "https://x.tn"]


def test_cors_desactive_donne_une_liste_vide(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "prod")
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "https://mcp.data.gov.tn")
    monkeypatch.setattr(main_mod.settings, "CORS_ENABLED", False)

    assert main_mod._origin_allowlist() == []


async def test_un_hote_inconnu_recoit_421(monkeypatch):
    """Protection Host : un DNS rebinding vers un hote inattendu doit echouer."""
    transport = httpx.ASGITransport(app=main_mod.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.data.gov.tn") as client:
        ok = await client.get("/health", headers={"host": "mcp.data.gov.tn"})
        ko = await client.get("/health", headers={"host": "attaquant.example"})

    assert ok.status_code == 200
    assert ko.status_code == 421


async def test_une_origine_non_autorisee_recoit_403(monkeypatch):
    """Avec une liste d'origines reelle, une origine tierce doit etre refusee."""
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "prod")
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "https://mcp.data.gov.tn")
    monkeypatch.setattr(main_mod.settings, "CORS_ENABLED", True)
    app = main_mod.create_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.data.gov.tn") as client:
        tierce = await client.get(
            "/health",
            headers={"host": "mcp.data.gov.tn", "origin": "https://attaquant.example"},
        )
        autorisee = await client.get(
            "/health",
            headers={"host": "mcp.data.gov.tn", "origin": "https://mcp.data.gov.tn"},
        )
        sans_origin = await client.get("/health", headers={"host": "mcp.data.gov.tn"})

    assert tierce.status_code == 403
    assert autorisee.status_code == 200
    # Un client MCP non navigateur n'envoie pas d'Origin : il doit passer.
    assert sans_origin.status_code == 200


async def test_le_joker_laisse_passer_toute_origine_en_local(monkeypatch):
    """Documentation du defaut de developpement : '*' n'est bloque qu'en prod."""
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "local")
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "*")
    app = main_mod.create_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mcp.data.gov.tn") as client:
        reponse = await client.get(
            "/health",
            headers={"host": "mcp.data.gov.tn", "origin": "https://attaquant.example"},
        )

    assert reponse.status_code == 200


def test_le_joker_refuse_de_demarrer_en_prod(monkeypatch):
    monkeypatch.setattr(main_mod.settings, "MCP_ENV", "prod")
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "*")
    monkeypatch.setattr(main_mod.settings, "CORS_ENABLED", True)

    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        main_mod.create_app()
