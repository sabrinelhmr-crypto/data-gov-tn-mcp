"""Tests unitaires pour l'outil get_metrics (C3)."""

import importlib

from helpers.api_client import DatagovAPIError
from tools.get_metrics import get_metrics

metrics_mod = importlib.import_module("tools.get_metrics")

PROD = "prod"


def _package(resources=None, title="Prix immobiliers"):
    return {
        "success": True,
        "result": {
            "id": "abc-123",
            "title": title,
            "resources": resources
            if resources is not None
            else [
                {"id": "res-1", "name": "Donnees 2024", "downloads_count": 42},
                {"id": "res-2", "name": "Donnees 2025", "downloads_count": 27},
            ],
        },
    }


async def test_environnement_demo_refuse(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", "demo")
    out = await get_metrics()
    assert "environnement production" in out


async def test_periode_invalide(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)
    out = await get_metrics(period="1m")
    assert "Periode '1m' non valide" in out
    assert "7d" in out


async def test_metriques_dataset(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)

    async def handler(params):
        return _package()

    datagov.handler = handler

    out = await get_metrics(dataset_id="abc-123")

    assert "Indicateurs d'usage" in out
    assert "Periode : 30d" in out
    assert "Dataset : Prix immobiliers" in out
    assert "1. Donnees 2024 : 42 telechargement(s)" in out
    assert "2. Donnees 2025 : 27 telechargement(s)" in out
    assert "Total des telechargements : 69" in out
    assert "Vues : indisponible via l'API" in out
    assert "Reutilisations : indisponible via l'API" in out
    assert "Tendance : indisponible via l'API" in out


async def test_metriques_dataset_sans_ressources(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)

    async def handler(params):
        return _package(resources=[])

    datagov.handler = handler

    out = await get_metrics(dataset_id="abc-123")
    assert "ne contient aucune ressource" in out


async def test_metriques_nom_long_et_telechargements_absents(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)

    async def handler(params):
        return _package(
            resources=[
                {"id": "res-1", "name": "Y" * 120, "downloads_count": None},
            ]
        )

    datagov.handler = handler

    out = await get_metrics(dataset_id="abc-123")
    assert "Y" * 77 + "..." in out
    assert "indisponible telechargement(s)" in out
    assert "Total des telechargements : 0" in out


async def test_metriques_dataset_introuvable(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)

    async def handler(params):
        raise DatagovAPIError("Not found: abc")

    datagov.handler = handler

    out = await get_metrics(dataset_id="abc-introuvable")
    assert "Dataset introuvable" in out


async def test_metriques_portail(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)

    async def path_handler(path, params):
        if path == "/action/package_search":
            return {"success": True, "result": {"count": 2904, "results": []}}
        if path == "/action/organization_list":
            return {"success": True, "result": [{"name": "org-a"}, {"name": "org-b"}]}
        if path == "/action/group_list":
            return {"success": True, "result": [{"name": "grp-a"}]}
        raise DatagovAPIError(f"Chemin inattendu: {path}")

    datagov.path_handler = path_handler

    out = await get_metrics(period="7d")

    assert "Periode : 7d" in out
    assert "Datasets disponibles : 2 904" in out
    assert "Organisations : 2" in out
    assert "Themes (groupes) : 1" in out
    assert "Telechargements globaux : indisponible via l'API" in out


async def test_metriques_portail_erreur_api(datagov, monkeypatch):
    monkeypatch.setattr(metrics_mod.settings, "DATAGOV_API_ENV", PROD)

    async def path_handler(path, params):
        raise DatagovAPIError("HTTP 500")

    datagov.path_handler = path_handler

    out = await get_metrics()
    assert "Impossible de recuperer les indicateurs du portail" in out
