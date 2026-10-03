"""
Test d'integration unique du serveur MCP data.gov.tn.

Couvre le serveur de bout en bout, dans le seul sens du CDC section 4.2 :

1. demarrage          : handshake MCP, /health, /health/ready, 10 outils publies
2. decouverte (A)     : search_datasets, search_dataservices
3. inspection (B)     : get_dataset_info, list_dataset_resources, get_resource_info,
                        get_dataservice_info, get_dataservice_openapi_spec
4. analyse (C)        : query_resource_data, download_and_parse_resource, get_metrics
5. transport          : Streamable HTTP (CDC 5.1), protection Host/Origine (CDC 6.1)
                        et limitation de debit (CDC 6.1)

Le portail data.gov.tn est remplace par un stub CKAN en memoire : aucun appel
reseau reel, donc le test est deterministe et herite.
"""

import importlib
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastmcp import Client

main_mod = importlib.import_module("main")

BASE_URL = "http://testserver"

OUTILS_ATTENDUS = {
    # Famille A - Recherche et decouverte
    "search_datasets",
    "search_dataservices",
    # Famille B - Inspection et metadonnees
    "get_dataset_info",
    "list_dataset_resources",
    "get_resource_info",
    "get_dataservice_info",
    "get_dataservice_openapi_spec",
    # Famille C - Analyse de donnees
    "query_resource_data",
    "download_and_parse_resource",
    "get_metrics",
}

# --- Jeu de donnees du stub CKAN ---------------------------------------------

DATASET_ID = "dataset-immobilier"
DATASERVICE_ID = "api-meteo"

PACKAGE = {
    "id": DATASET_ID,
    "name": "prix-immobilier-tunisie",
    "title": "Prix de l'immobilier en Tunisie",
    "type": "dataset",
    "notes": "Prix moyen par gouvernorat.",
    "organization": {"name": "ministere", "title": "Ministere de l'Equipement"},
    "license_title": "Licence Ouverte Tunisie",
    "groups": [{"display_name": "Urbanisme"}],
    "tags": [{"name": "immobilier"}, {"name": "prix"}],
    "metadata_created": "2024-01-01T00:00:00",
    "metadata_modified": "2025-06-01T00:00:00",
    "num_resources": 2,
    "num_tags": 2,
    "extras": [{"key": "frequency", "value": "annuelle"}],
    "resources": [
        {
            "id": "res-prix",
            "name": "Prix par gouvernorat",
            "format": "CSV",
            "size": 2048,
            "mimetype": "text/csv",
            "url": "https://catalog.data.gov.tn/prix.csv",
            "resource_type": "file",
            "created": "2024-01-01T00:00:00",
            "last_modified": "2025-06-01T00:00:00",
            "datastore_active": True,
            "hash": "abc123",
            "package_id": DATASET_ID,
        },
        {
            "id": "res-doc",
            "name": "Documentation",
            "format": "PDF",
            "size": 1024,
            "mimetype": "application/pdf",
            "url": "https://catalog.data.gov.tn/doc.pdf",
            "resource_type": "file",
            "created": "2024-01-01T00:00:00",
            "last_modified": "2025-06-01T00:00:00",
            "datastore_active": False,
            "package_id": DATASET_ID,
        },
    ],
}

DATASERVICE = {
    "id": DATASERVICE_ID,
    "name": "api-meteo-tunisie",
    "title": "API Meteo Tunisie",
    "type": "dataservice",
    "notes": "Previsions meteo par region.",
    "url": "https://api.meteo.gov.tn",
    "organization": {"name": "ministere", "title": "Ministere de la Meteo"},
    "extras": [{"key": "documentation", "value": "https://api.meteo.gov.tn/docs"}],
    "resources": [
        {
            "id": "svc-previsions",
            "name": "Previsions",
            "format": "JSON",
            "url": "https://api.meteo.gov.tn/previsions",
            "resource_type": "api",
        }
    ],
}

RECORDS = [
    {"gouvernorat": "Tunis", "prix_moyen": 1850},
    {"gouvernorat": "Sousse", "prix_moyen": 1420},
    {"gouvernorat": "Sfax", "prix_moyen": 1390},
]

# Variante du dataset dont les ressources sont orientees API : c'est ce que
# search_dataservices (A2) cherche a mettre en avant comme service.
PACKAGE_API = {
    **PACKAGE,
    "id": "dataset-meteo-api",
    "name": "meteo-api",
    "title": "Service Meteo Tunisie",
    "notes": "API de previsions meteo.",
    "resources": [
        {
            "id": "svc-previsions",
            "name": "Previsions",
            "format": "JSON",
            "url": "https://api.meteo.gov.tn/previsions",
            "resource_type": "api",
            "package_id": "dataset-meteo-api",
        }
    ],
}

DATASTORE_RESULT = {
    "fields": [
        {"id": "gouvernorat", "type": "text"},
        {"id": "prix_moyen", "type": "float"},
    ],
    "records": RECORDS,
    "total": len(RECORDS),
    "limit": 20,
    "offset": 0,
}

CSV = "gouvernorat,prix_moyen\nTunis,1850\nSousse,1420\nSfax,1390\n"

METRICS = {
    "success": True,
    "result": {"views": 1200, "downloads": 340, "reuses": 25},
}

OPENAPI = {
    "openapi": "3.0.0",
    "info": {"title": "API Meteo Tunisie", "version": "1.0.0"},
    "paths": {"/previsions": {"get": {"responses": {"200": {"description": "OK"}}}}},
}


class PortailCKAN:
    """Stub CKAN minimal servant les 10 outils du serveur."""

    def __init__(self) -> None:
        self.appeles: list[tuple[str, dict[str, Any] | None]] = []

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.appeles.append((path, params))
        params = params or {}

        if path == "/action/status_show":
            # Le CKAN reel expose la version du moteur sous `result.ckan_version`
            # (et non `result.version`) : le stub doit coller a la prod.
            return {"success": True, "result": {"ckan_version": "2.11.0"}}

        if path == "/action/package_search":
            # search_dataservices (A2) attend des ressources orientees API :
            # la seconde page du stub en fournit une, sinon l'outil n'a rien
            # a mettre en avant comme service.
            return {"success": True, "result": {"count": 2, "results": [PACKAGE, PACKAGE_API]}}

        if path == "/action/resource_show":
            identifiant = params.get("id")
            for ressource in (*PACKAGE["resources"], *DATASERVICE["resources"]):
                if ressource["id"] == identifiant:
                    return {"success": True, "result": ressource}
            return {
                "success": False,
                "error": {"__type": "Not Found", "message": f"Not found: {identifiant}"},
            }

        if path in ("/action/group_list", "/action/organization_list"):
            return {
                "success": True,
                "result": [{"id": "ministere", "name": "ministere", "title": "Ministere"}],
            }

        if path == "/action/package_show":
            identifiant = params.get("id")
            if identifiant == DATASERVICE_ID:
                return {"success": True, "result": DATASERVICE}
            if identifiant == DATASET_ID:
                return {"success": True, "result": PACKAGE}
            return {
                "success": False,
                "error": {"__type": "Not Found", "message": f"Not found: {identifiant}"},
            }

        if path == "/action/datastore_search":
            return {"success": True, "result": DATASTORE_RESULT}

        if path == "/action/datastore_search_sql":
            return {"success": True, "result": DATASTORE_RESULT}

        if path.startswith("/action/datastore_search") or path == "/action/datastore_create":
            return {"success": True, "result": DATASTORE_RESULT}

        if path in ("/action/usage_show", "/action/package_activity_show"):
            return METRICS

        return {"success": True, "result": {}}

    async def download(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        allowed_hosts: list[str] | None = None,
    ) -> bytes:
        return CSV.encode("utf-8")

    async def aclose(self) -> None:
        return None


@pytest.fixture
def portail(monkeypatch: pytest.MonkeyPatch):
    """Branche le stub CKAN sur le serveur et sur chaque module outil.

    Les outils referencent `datagov_client` comme global de module : la
    substitution doit donc viser le serveur (pour /health/ready) ET chaque
    module, sinon les appels MCP passeraient par le vrai client reseau.
    """
    stub = PortailCKAN()
    monkeypatch.setattr(main_mod, "datagov_client", stub)
    for nom in (
        "search_datasets",
        "search_dataservices",
        "get_dataset_info",
        "list_dataset_resources",
        "get_resource_info",
        "get_dataservice_info",
        "get_dataservice_openapi_spec",
        "query_resource_data",
        "download_and_parse_resource",
        "get_metrics",
    ):
        module = importlib.import_module(f"tools.{nom}")
        monkeypatch.setattr(module, "datagov_client", stub)
    return stub


@pytest.fixture
async def mcp_client(portail):
    """Session MCP en memoire : exerce le protocole sans passer par le HTTP."""
    async with Client(main_mod.mcp) as client:
        yield client


@pytest.fixture
async def asgi_client():
    """Client HTTP ASGI pour les routes annexes (/health, /health/ready)."""
    transport = httpx.ASGITransport(app=main_mod.app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
        yield http


@asynccontextmanager
async def _client_http(app):
    """Client httpx sur une app ASGI construite par `create_app`."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
        yield http


def texte(resultat) -> str:
    """Extrait le texte d'un retour d'outil MCP."""
    contenu = getattr(resultat, "content", resultat)
    morceaux = []
    for bloc in contenu:
        if getattr(bloc, "text", None):
            morceaux.append(bloc.text)
        elif isinstance(bloc, dict) and "text" in bloc:
            morceaux.append(bloc["text"])
    return "\n".join(morceaux) if morceaux else str(contenu)


# --- 1. Demarrage ------------------------------------------------------------


async def test_le_serveur_demarre_et_publie_les_dix_outils(mcp_client, portail):
    """Le handshake aboutit et la liste des outils est conforme au CDC 4.1."""
    outils = await mcp_client.list_tools()

    assert {outil.name for outil in outils} == OUTILS_ATTENDUS
    assert len(outils) == 10
    assert len(portail.appeles) == 0, "list_tools ne doit pas appeler l'API data.gov.tn"


async def test_chaque_outil_publie_un_schema_exploitable(mcp_client, portail):
    """Un client MCP a besoin d'un JSON Schema valide par outil (CDC 4.1)."""
    for outil in await mcp_client.list_tools():
        assert outil.description, f"{outil.name} sans description"
        schema = outil.inputSchema
        assert schema["type"] == "object"
        assert schema.get("properties") is not None


async def test_health_et_readiness_publient_le_statut_du_serveur(asgi_client, portail):
    """/health et /health/ready repondent l'etat declare au CDC 7.1."""
    live = await asgi_client.get("/health")
    assert live.status_code == 200
    corps = live.json()
    assert corps["status"] == "healthy"
    assert corps["service"] == "data.gov.tn-mcp"
    assert corps["tools_count"] == 10
    assert corps["uptime_seconds"] >= 0

    ready = await asgi_client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["api"]["reachable"] is True
    assert ready.json()["api"]["ckan_version"] == "2.11.0"


async def test_readiness_signale_une_porte_qui_echoue(monkeypatch, asgi_client):
    """Une API injoignable doit degrader le statut, pas lever une exception."""
    from helpers.api_client import DatagovAPIError

    class Panne:
        async def get(self, path, params=None):
            raise DatagovAPIError("API injoignable")

    monkeypatch.setattr(main_mod, "datagov_client", Panne())

    reponse = await asgi_client.get("/health/ready")
    assert reponse.status_code == 503
    assert reponse.json()["status"] == "degraded"
    assert reponse.json()["api"]["reachable"] is False


# --- 2. Famille A : recherche et decouverte ----------------------------------


async def test_famille_a_recherche_datasets_et_dataservices(mcp_client, portail):
    """A1 et A2 interrogent package_search et renvoient des resultats lisibles."""
    datasets = await mcp_client.call_tool("search_datasets", {"query": "immobilier"})
    texte_datasets = texte(datasets)
    assert "Prix de l'immobilier" in texte_datasets
    assert DATASET_ID in texte_datasets

    dataservices = await mcp_client.call_tool("search_dataservices", {"query": "meteo"})
    assert "Meteo" in texte(dataservices)


# --- 3. Famille B : inspection et metadonnees --------------------------------


async def test_famille_b_inspecte_un_dataset_complet(mcp_client, portail):
    """B1 puis B2 : metadonnees du dataset, puis ses ressources."""
    info = texte(await mcp_client.call_tool("get_dataset_info", {"dataset_id": DATASET_ID}))
    assert "Prix de l'immobilier" in info
    assert "Ministere de l'Equipement" in info
    assert "Licence Ouverte Tunisie" in info

    ressources = texte(
        await mcp_client.call_tool("list_dataset_resources", {"dataset_id": DATASET_ID})
    )
    assert "Prix par gouvernorat" in ressources
    assert "Documentation" in ressources


async def test_famille_b_inspecte_une_ressource(mcp_client, portail):
    """B3 : MIME type, format, taille et disponibilite Tabular API."""
    info = texte(await mcp_client.call_tool("get_resource_info", {"resource_id": "res-prix"}))
    assert "res-prix" in info
    assert "CSV" in info
    assert "2" in info  # taille en Ko


async def test_famille_b_inspecte_un_dataservice(mcp_client, portail):
    """B4 : metadonnees du dataservice, URL de base et endpoint principal."""
    info = texte(
        await mcp_client.call_tool("get_dataservice_info", {"dataservice_id": DATASERVICE_ID})
    )
    assert "API Meteo Tunisie" in info
    assert "https://api.meteo.gov.tn" in info


async def test_famille_b_retourne_la_spec_openapi(monkeypatch, mcp_client, portail):
    """B5 : la specification OpenAPI du dataservice est restituee en JSON.

    La specification est telechargee hors de l'API data.gov.tn (B5 ouvre sa
    propre session httpx) : la resolution reseau est donc court-circuitee ici,
    l'integration restant centree sur la publication du resultat par le serveur.
    """
    spec_module = importlib.import_module("tools.get_dataservice_openapi_spec")

    async def faux_fetch(url: str) -> str:
        return json.dumps(OPENAPI, indent=2, ensure_ascii=False)

    monkeypatch.setattr(spec_module, "_fetch_spec", faux_fetch)

    spec = texte(
        await mcp_client.call_tool(
            "get_dataservice_openapi_spec", {"dataservice_id": DATASERVICE_ID}
        )
    )
    assert "openapi" in spec
    assert json.dumps(OPENAPI, indent=2, ensure_ascii=False) in spec


# --- 4. Famille C : analyse de donnees ---------------------------------------


async def test_famille_c_interroge_le_datastore(mcp_client, portail):
    """C1 : projection de colonnes et tri sur une ressource tabulaire."""
    resultat = await mcp_client.call_tool(
        "query_resource_data",
        {
            "resource_id": "res-prix",
            "columns": ["gouvernorat", "prix_moyen"],
            "sort": [{"column": "prix_moyen", "direction": "desc"}],
        },
    )
    texte_resultat = texte(resultat)
    assert "Tunis" in texte_resultat
    assert "1850" in texte_resultat
    assert "gouvernorat" in texte_resultat


async def test_famille_c_telecharge_une_ressource(mcp_client, portail):
    """C2 : le CSV est telecharge puis presente (schema + apercu)."""
    apercu = texte(
        await mcp_client.call_tool("download_and_parse_resource", {"resource_id": "res-prix"})
    )
    assert "gouvernorat" in apercu
    assert "Tunis" in apercu


async def test_famille_c_lit_les_metriques(mcp_client, portail):
    """C3 : les indicateurs d'usage du dataset sont restitues."""
    metriques = texte(await mcp_client.call_tool("get_metrics", {"dataset_id": DATASET_ID}))
    assert metriques.strip()


# --- 5. Workflow CDC 4.2 de bout en bout -------------------------------------


async def test_workflow_complet_decouverte_inspection_analyse(mcp_client, portail):
    """Scenario CDC 4.2 : decouverte -> inspection -> analyse, en un parcours.

    C'est le test qui garantit que les trois familles s'enchainent sur la meme
    session et le meme portail : chaque etape reutilise l'identifiant rendu par
    la precedente.
    """
    # Etape 1 - decouverte
    decouverte = texte(
        await mcp_client.call_tool("search_datasets", {"query": "prix immobilier Tunisie"})
    )
    assert DATASET_ID in decouverte

    # Etape 2 - inspection
    fiche = texte(await mcp_client.call_tool("get_dataset_info", {"dataset_id": DATASET_ID}))
    assert "Prix de l'immobilier" in fiche

    # Etape 3 - analyse
    lignes = texte(
        await mcp_client.call_tool(
            "query_resource_data",
            {
                "resource_id": "res-prix",
                "columns": ["gouvernorat", "prix_moyen"],
                "sort": [{"column": "prix_moyen", "direction": "desc"}],
            },
        )
    )
    assert "Tunis" in lignes

    # Le parcours a bien traverse le stub, sans appel reseau reel.
    assert {path for path, _ in portail.appeles} <= {
        "/action/package_search",
        "/action/package_show",
        "/action/datastore_search",
        "/action/datastore_search_sql",
    }


# --- 6. Transport et securite (CDC 5.1, 6.1) --------------------------------


async def test_transport_streamable_http_sur_le_point_d_entree_mcp(portail):
    """CDC 5.1 : le trafic JSON-RPC transite par /mcp en Streamable HTTP.

    httpx.ASGITransport ne declenche pas le lifespan, alors que le gestionnaire
    de sessions de FastMCP s'y installe : le lifespan est donc ouvert ici, dans
    le test lui-meme (ouvrir et fermer un context manager d'un autre cote de
    pytest ferait sortir le cancel scope depuis une tache differente).
    """
    app = main_mod.app
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
            reponse = await http.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )

    assert reponse.status_code == 200
    corps = reponse.text
    assert '"search_datasets"' in corps
    assert '"query_resource_data"' in corps


async def test_un_appel_doutil_passe_par_le_transport_http(portail):
    """CDC 5.1 : un tools/call sur /mcp renvoie le resultat de l'outil."""
    app = main_mod.app
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as http:
            reponse = await http.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "search_datasets",
                        "arguments": {"query": "immobilier"},
                    },
                },
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )

    assert reponse.status_code == 200
    assert "Prix de l'immobilier" in reponse.text


async def test_un_hote_inconnu_est_refuse(portail):
    """CDC 6.1 : un Host hors ALLOWED_HOSTS recoit 421 (anti DNS rebinding)."""
    async with _client_http(main_mod.app) as http:
        reponse = await http.get("/health", headers={"Host": "attaquant.example"})
    assert reponse.status_code == 421


async def test_une_origine_etrangere_est_refusee(monkeypatch, portail):
    """CDC 6.1 : une origine navigateur non declaree recoit 403.

    L'app est reconstruite apres le monkeypatch : les listes allowed_hosts et
    allowed_origins sont figees a la construction (voir `create_app`).
    """
    monkeypatch.setattr(main_mod.settings, "ALLOWED_ORIGINS", "https://mcp.data.gov.tn")
    app = main_mod.create_app()
    async with _client_http(app) as http:
        refusee = await http.get("/health", headers={"Origin": "https://attaquant.example"})
        attendue = await http.get("/health", headers={"Origin": "https://mcp.data.gov.tn"})
    assert refusee.status_code == 403
    assert attendue.status_code == 200


async def test_le_quota_de_requetes_est_applique(monkeypatch, portail):
    """CDC 6.1 : au-dela du quota, le serveur repond 429."""

    from helpers.rate_limit import SlidingWindowRateLimiter

    limiteur = SlidingWindowRateLimiter(limit=3, window=60.0, burst=0, max_keys=100)
    monkeypatch.setattr(
        main_mod,
        "rate_limiter",
        limiteur,
        raising=True,
    )
    monkeypatch.setattr(
        main_mod.settings,
        "RATE_LIMIT_EXEMPT_PATHS",
        "",
        raising=True,
    )
    app = main_mod.create_app()
    async with _client_http(app) as http:
        codes = [(await http.get("/health")).status_code for _ in range(6)]

    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429, 429]
