# Serveur MCP Open Data Tunisie

<div dir="rtl">

# خادم بروتوكول سياق النموذج للبيانات المفتوحة في تونس

</div>

**data.gov.tn-mcp** — Serveur [Model Context Protocol](https://modelcontextprotocol.io)
pour le portail national des données ouvertes de la Tunisie
([data.gov.tn](https://catalog.data.gov.tn/fr/dataset)).

Serveur **en lecture seule** (phase 1) : il expose des *outils* que vos assistants
IA compatibles MCP (Claude, ChatGPT, Mistral, Cursor, VS Code, Gemini) peuvent
appeler pour rechercher et analyser les données publiques tunisiennes en langage
naturel.

> **English summary** — Read-only MCP server for Tunisia's national open data
> portal. Exposes standardised tools over the portal's CKAN API via Streamable
> HTTP, so MCP-compatible AI assistants can search, inspect and analyse Tunisian
> public data in natural language.
>
> **ملخّص بالعربية** — خادم للقراءة فقط يتيح الوصول إلى البوابة الوطنية
> للبيانات المفتوحة في تونس عبر بروتوكول سياق النموذج (MCP)، ويوفّر أدوات
> موحّدة للبحث في البيانات التونسية العامة وتحليلها.

---

## État d'avancement / حالة الإنجاز / Status

> ⚠️ **Lisez cette section avant de promettre des outils à vos utilisateurs.**
> Le cahier des charges (CDC §4.1) décrit **10 outils** — son texte en annonce
> « 9 », mais la liste en contient 10. À ce jour, **8 sont enregistrés** ;
> B4 et B5 sont écrits et testés mais volontairement **non enregistrés**, car le
> portail ne publie pas d'entité `dataservice`. Ce tableau fait autorité, de
> même que `tools_count` renvoyé par `/health`.
>
> ⚠️ **اقرأ هذا القسم قبل أن تَعِد المستخدمين بأي أدوات.** يصف كرّاس الشروط
> (القسم 4.1) **10 أدوات** (نصّه يذكر « 9 »)، غير أنّ **8 منها مطبّقة
> ومسجّلة**؛ أما الأداتان B4 و B5 فمكتوبتان ومختبَرتان لكنهما غير مسجّلتين.
>
> ⚠️ **Read this section before promising tools to your users.** The
> specification lists **10 tools** (its own text says 9); **8 are registered**.

| # | Tool | Famille | Statut / الحالة | Status |
|---|------|---------|-----------------|--------|
| A1 | `search_datasets` | Recherche | ✅ Implémenté | Live |
| A2 | `search_dataservices` | Recherche | ✅ Implémenté | Live |
| B1 | `get_dataset_info` | Inspection | ✅ Implémenté (FR/AR/EN) | Live |
| B2 | `list_dataset_resources` | Inspection | ✅ Implémenté (FR/AR/EN) | Live |
| B3 | `get_resource_info` | Inspection | ✅ Implémenté (FR/AR/EN) | Live |
| B4 | `get_dataservice_info` | Inspection | ⚠️ Codé, non enregistré | Blocked |
| B5 | `get_dataservice_openapi_spec` | Inspection | ⚠️ Codé, non enregistré | Blocked |
| C1 | `query_resource_data` | Analyse | ✅ Implémenté | Live |
| C2 | `download_and_parse_resource` | Analyse | ✅ Implémenté | Live |
| C3 | `get_metrics` | Analyse | ✅ Implémenté | Live |

L'endpoint `GET /health` renvoie `tools_count`, qui reflète ce nombre réel.

La documentation trilingue (FR/AR/EN) de chaque outil se trouve dans
**[docs/api_reference.md](docs/api_reference.md)**.

---

## Prérequis

- **Python 3.13** ou supérieur — `pyproject.toml` impose `requires-python = ">=3.13"`
  (le CDC mentionne 3.12+, mais le code et la CI ciblent 3.13 ; ne descendez pas
  en dessous sans ajuster `ruff.target-version` et la CI).
- **Git**
- **Docker** + **Docker Compose** (uniquement pour le mode conteneurisé)

Aucune clé API n'est nécessaire : l'API CKAN de `data.gov.tn` est publique et
l'authentification est facultative en phase 1 (CDC §6.3, Décret 2021-3 art. 9).

## Installation

```bash
# 1. Récupérer le projet
git clone https://github.com/sabrinelhmr-crypto/data-gov-tn-mcp.git
cd data-gov-tn-mcp

# 2. Créer l'environnement virtuel puis l'activer
python -m venv venv

# Windows PowerShell :
venv\Scripts\Activate.ps1
# Linux / macOS :
# source venv/bin/activate

# 3. Installer le projet et ses dépendances de développement
pip install -e ".[dev]"
```

Le nom de distribution est `datagouv-mcp-tn` (voir `pyproject.toml`), le service
s'identifie comme `data.gov.tn-mcp` (voir `main.py`).

## Lancer le serveur en local

```bash
# Copier le modèle de configuration (facultatif : des valeurs par défaut suffisent)
cp .env.example .env      # Linux / macOS
copy .env.example .env    # Windows

# Démarrer
python main.py
```

Le serveur écoute sur `http://0.0.0.0:8000` par défaut.

| Endpoint | Méthode | Rôle |
|----------|---------|------|
| `/mcp` | POST | Trafic JSON-RPC 2.0 (transport Streamable HTTP) |
| `/health` | GET | *Liveness* — le processus répond. Aucun appel externe. |
| `/health/ready` | GET | *Readiness* — teste l'accès à l'API `data.gov.tn`. |

### Vérifier que ça marche

```bash
curl http://localhost:8000/health
```

Réponse réelle observée en local :

```json
{
  "status": "healthy",
  "service": "data.gov.tn-mcp",
  "version": "0.1.0",
  "env": "local",
  "data_env": "prod",
  "uptime_since": "2026-09-27T08:03:55.982321+00:00",
  "uptime_seconds": 0.0,
  "timestamp": "2026-09-27T08:03:56.005551+00:00",
  "tools_count": 8
}
```

`/health/ready` renvoie `200` quand l'API CKAN répond, et `503` avec
`"status": "degraded"` sinon. Exemple réel observé lorsque l'API est injoignable
(p. ex. chaîne de certification TLS incomplète sur le poste) :

```json
{
  "status": "degraded",
  "service": "data.gov.tn-mcp",
  "version": "0.1.0",
  "env": "local",
  "data_env": "prod",
  "api": {
    "reachable": false,
    "error": "Erreur reseau vers data.gov.tn (/action/status_show) : ..."
  }
}
```

### Lancer les tests

```bash
python -m pytest
```

> ✅ **La suite est verte.** Les **235 tests** passent et la couverture atteint
> **96,7 %**, au-dessus du seuil de 90 %. Voir
> [CONTRIBUTING.md](CONTRIBUTING.md#4-tests).

## Configuration par variables d'environnement

La configuration est lue par `config.py` (Pydantic Settings) depuis le fichier
`.env`. Les noms de variables sont **sensibles à la casse** (`case_sensitive=True`).

### Serveur MCP

| Variable | Défaut | Type | Description |
|----------|--------|------|-------------|
| `MCP_HOST` | `0.0.0.0` | str | Interface d'écoute. Mettre `127.0.0.1` en local. |
| `MCP_PORT` | `8000` | int | Port HTTP. |
| `MCP_ENV` | `local` | `local` \| `preprod` \| `prod` \| `demo` | Environnement applicatif. |

### API data.gov.tn

| Variable | Défaut | Type | Description |
|----------|--------|------|-------------|
| `DATAGOV_API_ENV` | `prod` | `prod` \| `demo` | Environnement de données. `get_metrics` est refusé hors `prod`. |
| `DATAGOV_API_BASE_URL` | `https://catalog.data.gov.tn/api/3` | str | URL de base de l'API CKAN. |
| `DATAGOV_API_KEY` | *(vide)* | str | Facultatif en phase 1 (lecture seule). |
| `DATAGOV_API_VERIFY_SSL` | `true` | bool | Vérification TLS. |

> ⚠️ **L'URL du CDC est périmée.** Le CDC §5.2 indique
> `https://www.data.gov.tn/api/3`, qui renvoie `404`. L'API CKAN réellement en
> service est sur `https://catalog.data.gov.tn/api/3` (cf. `.env.example`).
>
> ⚠️ **`DATAGOV_API_VERIFY_SSL=false` n'est à utiliser que sur un poste de
> développement** dont le magasin de certificats CA est incomplet (proxy
> d'entreprise, conteneur minimal). Ne jamais le désactiver en production.

### Logging

| Variable | Défaut | Type | Description |
|----------|--------|------|-------------|
| `LOG_LEVEL` | `INFO` | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR`\|`CRITICAL` | Niveau des logs. |

Les logs sont émis au format **JSON** sur `stdout` (`logging_config.py`, via
`python-json-logger`) : `asctime`, `levelname`, `name`, `message`.

### Monitoring

| Variable | Défaut | Type | Description |
|----------|--------|------|-------------|
| `SENTRY_DSN` | *(vide)* | str | DSN Sentry. |
| `SENTRY_SAMPLE_RATE` | `1.0` | float | Taux d'échantillonnage (0.0–1.0). |
| `MATOMO_URL` | *(vide)* | str | URL de l'instance Matomo. |
| `MATOMO_SITE_ID` | *(vide)* | str | ID de site Matomo. |

> ⚠️ **Non fonctionnels à ce jour.** `sentry-sdk` n'est pas une dépendance et le
> SDK Sentry n'est jamais initialisé ; `helpers/matomo.py` est vide. Les
> variables sont lues et validées, mais aucun événement n'est envoyé. Le CDC §7
> les exige : c'est une dette connue, pas une configuration manquante de votre
> part.

### Sécurité

| Variable | Défaut | Type | Description |
|----------|--------|------|-------------|
| `ALLOWED_HOSTS` | `data.gov.tn,www.data.gov.tn,catalog.data.gov.tn,mcp.data.gov.tn` | str | `Host` acceptés ; un `Host` inconnu reçoit **421**. |
| `ALLOWED_ORIGINS` | `*` | str | Origines navigateur acceptées ; une origine tierce reçoit **403**. `*` est **refusé au démarrage** si `MCP_ENV=prod`. |
| `CORS_ENABLED` | `true` | bool | `false` n'accepte aucune origine étrangère. |
| `DOWNLOAD_ALLOWED_HOSTS` | *(vide)* | str | Hôtes autorisés pour le téléchargement C2. Vide = tout hôte public. Jocker accepté : `*.data.gov.tn`. |

> ✅ ** appliqués.** `main.py` construit l'application avec
> `host_origin_protection=True`, `allowed_hosts` et `allowed_origins`. Le
> `True` est indispensable : sans lui FastMCP reçoit les listes mais
> n'installe pas le middleware de vérification (défaut `False`).
> Un client MCP non navigateur n'envoie pas d'`Origin` et n'est donc pas
> gené ; filter tout de même au reverse proxy (voir
> [docs/deployment.md](docs/deployment.md)).
>
> ⚠️ Le **rate limiting** (CDC §6.1 : 100 req/min/IP) n'est pas implémenté, ni
> la limite de payload de 1 Mo. Le rate limiting est à faire au reverse proxy.

### Performance

| Variable | Défaut | Type | Description |
|----------|--------|------|-------------|
| `MAX_PAGE_SIZE` | `100` | int | Taille de page maximale (bornée par l'outil). |
| `MAX_DOWNLOAD_SIZE_MB` | `100` | int | Taille de fichier maximale pour l'analyse. |
| `REQUEST_TIMEOUT` | `30` | int | Timeout des appels à l'API, en secondes. |

## Lancer le serveur avec Docker

```bash
# Construire et démarrer en arrière-plan
docker compose up -d --build

# Vérifier
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# Voir les logs
docker compose logs -f

# Arrêter
docker compose down
```

Le `docker-compose.yml` publishes `${MCP_PORT:-8000}:8000` et déclare un
`healthcheck` sur `/health/ready` (intervalle 30 s, timeout 10 s, 3 retries,
`start_period` 40 s) avec `restart: unless-stopped`.

Le `Dockerfile` part de `python:3.13-slim`, installe `curl` (nécessaire au
healthcheck), copie `pyproject.toml` + `README.md`, lance `pip install`, puis
copie le reste. `CMD ["python", "main.py"]`.

Pour le déploiement en production, voir **[docs/deployment.md](docs/deployment.md)**.

## Utilisation avec un client MCP

Le transport est **Streamable HTTP** uniquement (pas de STDIO, pas de SSE).
Configurez vos clients avec l'URL `/mcp` :

```json
{
  "mcpServers": {
    "data.gov.tn": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Les configurations Claude, ChatGPT, Mistral, Cursor et VS Code sont détaillées
dans le CDC (annexe A) et dans [docs/client_setup.md](docs/client_setup.md).

## Structure du projet

```
.
├── main.py                  # Point d'entrée FastMCP + routes /health
├── config.py                # Settings Pydantic (variables d'environnement)
├── logging_config.py        # Logs JSON sur stdout
├── pyproject.toml           # Dépendances, pytest, ruff
├── Dockerfile
├── docker-compose.yml
├── docs/
│   ├── api_reference.md     # Référence des outils (FR/AR/EN)
│   ├── architecture.md
│   ├── client_setup.md
│   └── deployment.md
├── helpers/
│   ├── api_client.py        # Client HTTP async vers l'API CKAN
│   ├── url_guard.py         # Garde-fou SSRF des téléchargements (C2)
│   ├── query_cleaner.py     # Nettoyage des termes génériques
│   ├── i18n.py              # Libellés FR/EN/AR (outils de la famille B)
│   ├── matomo.py            # ⬜ vide
│   └── pagination.py        # ⬜ vide
├── models/                  # ⬜ stubs Pydantic (phase 2)
├── tests/
└── tools/
    ├── __init__.py          # register_tools() — 8 outils enregistrés
    ├── search_datasets.py       # A1 ✅
    ├── search_dataservices.py   # A2 ✅
    ├── get_dataset_info.py      # B1 ✅
    ├── list_dataset_resources.py # B2 ✅
    ├── get_resource_info.py     # B3 ✅
    ├── get_dataservice_info.py  # B4 ⚠️ codé, non enregistré
    ├── get_dataservice_openapi_spec.py # B5 ⚠️ codé, non enregistré
    ├── query_resource_data.py   # C1 ✅
    ├── download_and_parse_resource.py # C2 ✅
    └── get_metrics.py           # C3 ✅
```

## Documentation

| Document | Contenu |
|----------|---------|
| [docs/api_reference.md](docs/api_reference.md) | Les 10 outils : but, paramètres, exemples (FR/AR/EN) |
| [docs/deployment.md](docs/deployment.md) | Guide de déploiement Docker en production |
| [docs/client_setup.md](docs/client_setup.md) | ⬜ à compléter (page vide) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Style de code, tests, workflow PR |

## Licence

MIT — prévue par le CDC (art. 14 : publication en Open Source).

> ⚠️ Le fichier `LICENSE` ne contient actuellement **qu'un commentaire
> d'en-tête**, pas le texte de la licence MIT. Il doit être complété avant toute
> publication publique du code, pour satisfaire l'art. 14 du Décret 2021-3.

## Conformité au Décret 2021-3

| Exigence | État |
|----------|------|
| art. 9 — publication sans authentification préalable | ✅ read-only, sans clé requise |
| art. 10 — formats ouverts (CSV, JSON, XML) | ⚠️ C1/C2 implémentés ; CSV et JSON vérifiés en direct, XML non couvert |
| art. 11 — licence de réutilisation | ⬜ licence tunisienne à produire (CDC livrable L7) |
| art. 14 — logiciel Open Source | ⬜ `LICENSE` à compléter |
| art. 16 — métadonnées trilingues AR/FR/EN | ⚠️ `lang` (`fr`/`en`/`ar`) sur B1–B5, libellés seuls ; familles A et C en français |
| art. 22 — URI pérennes | ✅ identifiants CKAN du portail |

Voir aussi `docs/architecture.md` (à compléter) et le CDC complet.
