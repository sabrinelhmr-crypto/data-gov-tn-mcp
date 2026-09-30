# Contribuer au projet

<div dir="rtl">

# المساهمة في المشروع

</div>

# Contributing

Merci de vouloir contribuer au serveur MCP Open Data Tunisie. Ce document
décrit les règles de code, l'exécution des tests et le processus de revue.

Thank you for contributing to the Tunisia Open Data MCP server. This document
covers code style, running the tests, and the pull request process.

---

## 1. État du projet — à lire en premier

Le projet est en cours de construction (CDC §9.2, sprints de 2 semaines). Connaître
l'état réel évite des PR qui documentent des choses inexistantes.

| Domaine | État |
|---------|-------|
| Famille A — `search_datasets`, `search_dataservices` | ✅ Implémenté et testé |
| Famille B — B1, B2, B3 | ✅ Implémenté et testé |
| Famille B — B4 `get_dataservice_info`, B5 `get_dataservice_openapi_spec` | ⚠️ Codés et testés, non enregistrés (`register_tools`) |
| Famille C — C1, C2, C3 | ✅ Implémenté et testé |
| `helpers/api_client.py` | ✅ `get()` + `download()` + `aclose()` |
| `helpers/query_cleaner.py` | ✅ |
| `helpers/i18n.py` | ✅ Libellés FR/EN/AR (familles B1–B5) |
| `helpers/matomo.py`, `helpers/pagination.py` | ⬜ Vides |
| `models/*.py` | ⬜ Stubs Pydantic (0 instruction) |
| Sentry, Matomo | ⬜ Non initialisés (`sentry-sdk` absent des dépendances) |
| CORS / `ALLOWED_HOSTS` | ✅ Appliqués (`host_origin_protection=True` → 421/403) |
| Rate limiting 100 req/min/IP | ⬜ Non implémenté (à faire au reverse proxy) |
| Garde-fou SSRF du téléchargement C2 | ✅ `helpers/url_guard.py` (schéma, IP publique, redirections) |
| Téléchargement C2 borné en mémoire | ✅ `stream()` + `max_bytes` |
| Conteneur non-root | ✅ `USER mcp` (uid 10001) |
| CI GitHub Actions | ✅ lint + tests |
| `LICENSE` | ⬜ Commentaire d'en-tête seul, pas de texte MIT |
| Couverture | ✅ 92,15 % — seuil de 90 % atteint |

**Règle d'or : ne documentez et n'annoncez que ce qui fonctionne.** Si un outil
n'est pas enregistré dans `tools/__init__.py`, il n'existe pas pour les
clients, quelle que soit la qualité de son fichier. `GET /health` renvoie
`tools_count`, qui doit correspondre au nombre d'`add_tool()` dans
`tools/__init__.py` : c'est le contrôle le plus rapide après une modification.

---

## 2. Environnement de développement

```bash
git clone https://github.com/sabrinelhmr-crypto/data-gov-tn-mcp.git
cd data-gov-tn-mcp

python -m venv venv
# Windows : venv\Scripts\Activate.ps1
# Linux/macOS : source venv/bin/activate

pip install -e ".[dev]"
pre-commit install
```

**Python 3.13 est requis** (`requires-python = ">=3.13"`). Le CDC mentionne
3.12+, mais le code et la CI ciblent 3.13.

Le nom de distribution est `datagouv-mcp-tn`, le service s'identifie
`data.gov.tn-mcp`.

---

## 3. Style de code

### Outils

| Outil | Rôle | Configuration |
|-------|------|---------------|
| **Ruff** | Lint + format | `line-length = 100`, `target-version = "py313"` |
| **ruff** rules | `E`, `W`, `F`, `I`, `UP`, `B` | `pyproject.toml` |
| **pre-commit** | Hooks au commit | `.pre-commit-config.yaml` |
| **pytest** | Tests | `asyncio_mode = "auto"`, seuil 90 % |

```bash
ruff check .          # lint
ruff check --fix .    # lint + corrections auto
ruff format .         # formatage
```

### Règles

- **Imports** : stdlib, puis tiers, puis local — séparés par une ligne vide
  (`I` de Ruff le vérifie). Les imports locaux sont **absolus** :
  `from config import settings`, jamais `from ..config`.
- **Types** : annotations systématiques. Python 3.13 → syntaxe moderne :
  `str | None` (pas `Optional[str]`), `list[str]` (pas `List[str]`).
- **Longueur** : 100 colonnes max.
- **Docstrings** : Google-style, en français, avec `Args:` / `Returns:` /
  `Raises:`. Documenter les paramètres, y compris leurs bornes.
- **Async** : tout accès réseau est `async` via
  `datagov_client` (`helpers/api_client.py`). **N'instanciez pas de
  `httpx.AsyncClient` ailleurs** — cela casse le pooling de connexions.
- **Aucune dépendance réseau dans les outils** : un outil appelle
  `datagov_client`, il ne construit pas d'URL.
- **Encodage** : UTF-8 partout. Le portail contient de l'arabe et des accents ;
  ne jamais utiliser `latin-1` en sortie.
- **Terminal** : si vous interrogez l'API depuis un script, capturez la sortie
  dans un fichier. PowerShell corrompt l'UTF-8 à l'affichage et peut vous faire
  croire à un bug d'encodage inexistant.

### Structure d'un outil

Un fichier par outil dans `tools/`, nommé comme l'outil :

```python
"""
Outil MCP B1 : get_dataset_info (Famille B - Inspection et Metadonnees).
<Description en une phrase, en français.>
"""

from helpers.api_client import DatagovAPIError, datagov_client

# Constantes de module en MAJUSCULES
_MAX_DESC_LEN = 300


def _truncate(text: str, limit: int) -> str:
    """Raccourcit un texte en ajoutant une ellipse."""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


async def get_dataset_info(dataset_id: str) -> str:
    """
    <Description en français, une phrase.>

    Args:
        dataset_id: Identifiant CKAN du dataset (UUID) ou slug (name).

    Returns:
        Un texte structuré listant les métadonnées.

    Raises:
        Ne lève pas : les erreurs sont rendues en texte (voir plus bas).
    """
    if not dataset_id or not dataset_id.strip():
        return "Veuillez fournir un identifiant de dataset."

    try:
        data = await datagov_client.get("/action/package_show", params={"id": dataset_id.strip()})
    except DatagovAPIError as exc:
        return f"Dataset introuvable pour '{dataset_id.strip()}' : {exc}"

    # ... construction de la sortie
    return "\n".join(lines)
```

Puis **l'enregistrer** dans `tools/__init__.py` — c'est l'étape la plus souvent
oubliée, et un outil non enregistré n'apparaît pas dans `tools/list` :

```python
from tools.get_dataset_info import get_dataset_info


def register_tools(mcp: FastMCP) -> None:
    mcp.add_tool(search_datasets)
    mcp.add_tool(search_dataservices)
    mcp.add_tool(get_dataset_info)  # <- sans ça, l'outil n'existe pas
```

Puis l'ajouter à la fixture de `tests/conftest.py` (voir §4) : un module outil
absent de cette liste échapperait à la substitution du client et toucherait
réellement le réseau.

### Conventions de sortie des outils

Les outils existants renvoient **du texte brut**, pas du JSON. Si vous ajoutez un
outil, suivez la convention existante sauf raison contraire à documenter :

- Valeurs `None` ⇒ champ omis.
- Textes tronqués à ~150 caractères avec `...`.
- Tailles de fichiers en unités lisibles (`Ko`, `Mo`).
- Une ligne vide entre chaque bloc.
- **Les erreurs sont rendues en texte**, jamais levées : un outil qui lève
  produit une erreur de protocole chez le client. Préférez toutefois un message
  explicite à un stacktrace.

---

## 4. Tests

```bash
python -m pytest                       # tout
python -m pytest tests/test_search_datasets.py -v
python -m pytest -k "query and not sql" # par expression
python -m pytest --no-cov              # sans couverture (plus rapide)
python -m pytest --cov=tools --cov-report=term-missing
```

Configuration (`pyproject.toml`) : `asyncio_mode = "auto"` (pas de marqueur
`@pytest.mark.asyncio` nécessaire), `testpaths = ["tests"]`,
`addopts = "--cov=. --cov-report=term-missing --cov-fail-under=90"`.

### ✅ La suite est verte, seuil de couverture atteint

```text
235 passed
Required test coverage of 90% reached. Total coverage: 96.70%
```

Le seuil a été atteint **en testant du vrai code**, pas en assouplissant la
configuration : `tools/search_datasets.py` (bornes de pagination, filtres
`fq`, repli sur la requête brute, réduction progressive, troncature du rendu),
`tools/query_resource_data.py` (validation des filtres et des tris,
littéraux SQL `NULL`/booléens, `IN`, pagination), `helpers/url_guard.py` et
`tools/get_dataset_info.py` sont à 100 %, tout comme `helpers/i18n.py`.

Le script `test_live_livraison.py` a été supprimé : il vivait à la racine du
dépôt, hors de `testpaths`, et `--cov=.` comptait ses instructions comme
non couvertes. Les tests correspondants vivent désormais dans
`tests/unit/` et `tests/test_transport_security.py`, donc réellement exécutés.

Ne modifiez pas `pyproject.toml` dans une PR de fonctionnalité : exclure ce
fichier de la couverture ferait monter le pourcentage **sans tester une seule
ligne de plus**. Préférez écrire les tests.

### Ce qui est couvert, et comment

| Fichier | Couverture | Remarque |
|---------|-----------|---------|
| `config.py` | 100 % | |
| `helpers/api_client.py` | 97 % | Lignes 35 et 138 (import tardif, redirect sans `Location`) |
| `helpers/i18n.py` | 100 % | |
| `helpers/query_cleaner.py` | 100 % | |
| `helpers/url_guard.py` | 100 % | |
| `logging_config.py` | 100 % | |
| `tools/__init__.py` | 100 % | |
| `tools/download_and_parse_resource.py` | 95 % | Gardes de format/encodage non testées |
| `tools/get_dataset_info.py` | 100 % | |
| `tools/get_metrics.py` | 100 % | |
| `tools/get_resource_info.py` | 92 % | Lignes 11-16 (import tardif), 26, 62-63 |
| `tools/list_dataset_resources.py` | 98 % | Ligne 44 |
| `tools/search_dataservices.py` | 98 % | Lignes 50 et 126 (bornes `page_size`) |
| `tools/query_resource_data.py` | 100 % | |
| `tools/search_datasets.py` | 100 % | |
| `tools/get_dataservice_info.py` (B4) | 94 % | Lignes 16-21 (import tardif) |
| `tools/get_dataservice_openapi_spec.py` (B5) | 86 % | Chemins de découverte de spécification partiellement testés |
| `main.py` | 94 % | Lignes 23-24 (`__main__`) et 134 (`mcp.run`) |
| `models/*.py`, `helpers/matomo.py`, `helpers/pagination.py` | — | Fichiers vides (0 instruction) |

Le pattern de test : `tests/conftest.py` fournit la fixture `datagov`, qui
remplace `datagov_client` par un faux client. **Ajoutez vos tests dans le même
esprit** — ne touchez jamais au réseau.

```python
async def test_mon_outil(datagov):
    async def handler(params):
        return {"result": {"count": 1, "results": [/* ... */]}}

    datagov.handler = handler
    resultat = await mon_outil(query="eau")
    assert "1 resultat(s)" in resultat
```

> ⚠️ `conftest.py` substitue le client dans les **8 modules enregistrés**
> (A1, A2, B1, B2, B3, C1, C2, C3). **Pour tout nouvel outil, ajoutez son
> module à la fixture**, sinon le test touchera réellement l'API.

### Tests d'intégration

`tests/integration/test_api_flow.py` est un stub. Le CDC prévoit un test
end-to-end. Il reste à écrire avec un marqueur d'exclusion pour ne pas casser
la CI :

```python
@pytest.mark.live
async def test_api_live(): ...
```

et dans `pyproject.toml` :

```toml
markers = ["live: tests nécessitant l'API data.gov.tn (exclus par défaut)"]
addopts = "--cov=. --cov-report=term-missing --cov-fail-under=90 -m 'not live'"
```

Le marqueur `live` n'est pas encore déclaré dans `pyproject.toml` : l'ajouter
dans la même PR que le test, sinon `pytest` émet un `PytestUnknownMarkWarning`
et, en configuration stricte, échoue.

---

## 5. Processus de Pull Request

### Branches

```
main                     # toujours déployable
feature/toolB            # une branche par outil ou par sujet
fix/query-filters
docs/api-reference
```

Nommez les branches `feature/`, `fix/` ou `docs/`. La CI se déclenche sur
`main` et `feature/*`.

### Workflow

1. **Créez la branche** depuis `main` à jour.
2. **Écrivez le code et les tests** dans le même commit logique.
3. **Passez les garde-fous en local** — c'est obligatoire, la CI ne pardonne pas :

   ```bash
   ruff check .
   ruff format --check .
   python -m pytest
   ```

4. **Mettez à jour la documentation** dans le même PR si le comportement change :
   - `README.md` — tableau de statut des outils
   - `docs/api_reference.md` — contrat de l'outil, dans les 3 langues
   - `.env.example` — si vous ajoutez une variable
5. **Ouvrez la PR** avec une description en français couvrant :
   - le problème ou l'objectif (référence au CDC si applicable) ;
   - la liste des fichiers modifiés ;
   - un exemple de requête et de réponse **réellement exécuté** ;
   - l'impact sur le périmètre (nouvel outil ? breaking change ?).
6. **Faites relire** (section 6).
7. **Corrigez** jusqu'à l'approbation, puis squash-merge.

### Messages de commit

Style imperatif, en français, préfixé par le type (repris de l'historique du
dépôt) :

```
feat: add get_dataservice_info tool (B4)
fix: clamp page_size to MAX_PAGE_SIZE in search_datasets
docs: add trilingual tool reference for families B and C
test: cover query_cleaner stopword folding
refactor: extract _truncate helper
```

### Critères de revue

Une PR n'est pas approuvée si :

- `ruff check` ou `ruff format --check` échoue ;
- la couverture passe sous 90 % ;
- un nouvel outil n'est pas enregistré dans `tools/__init__.py` ;
- un nouvel outil n'est pas documenté dans les 3 langues ;
- un outil non documenté est annoncé dans le README ;
- l'exemple de réponse n'a pas été réellement exécuté ;
- une variable d'env est ajoutée sans `.env.example` **et** README ;
- des secrets sont committés.

---

## 6. Revue de code

- **Un reviewer minimum**, deux pour le code qui touche `helpers/api_client.py`,
  la configuration ou la sécurité.
- **Revue dans les 48 h** ouvrées, sinon relance.
- Les commentaires de revue doivent être **actionnables**. Expliquez *pourquoi*,
  pas seulement *quoi*.
- L'auteur **répond à chaque commentaire**, y compris pour dire qu'il n'est pas
  d'accord — et explique pourquoi.
- Une PR n'est pas mergée avec des conversations non résolues.
- En cas de désaccord sur le fond (portée, choix technique), arbitrage en
  réunion plutôt qu'en fil de commentaires.

---

## 7. Documentation

La documentation est **trilingue** (français, arabe, anglais) en application du
Décret 2021-3 (art. 16). Pour tout outil ou variable ajouté :

- **FR** : la langue de travail et de référence du code ;
- **AR** : arabe standard, terms du Décret ;
- **EN** : pour la portée internationale.

Règles :

- Ne jamais inventer un exemple de sortie. Si l'outil n'est pas implémenté,
  écrivez « non disponible — outil non implémenté ».
- Un exemple doit être **capturé**, pas reconstitué de mémoire.
- Un tableau de statut fait autorité : README et `docs/api_reference.md` doivent
  être d'accord entre eux.

---

## 8. Sécurité

- **Ne jamais commiter de secrets.** `.env` est dans `.gitignore` — vérifiez
  aussi `.env.production`, `*.pem`, `*.key`.
- Si vous committez un secret par accident : **faites une rotation
  immédiatement**, un `git revert` ne suffit pas (l'historique conserve).
- Le code est public et sans authentification (Décret 2021-3 art. 9) : c'est
  délibéré. Ne le contournez pas en ajoutant une clé obligatoire.
- Toute donnée personnelle est interdite en entrée comme en sortie (RGPD,
  CDC §6.2). Le serveur ne doit stocker aucune requête utilisateur.
- Requêtes de recherche **anonymisées** dans les logs (CDC §6.2).
- `DATAGOV_API_VERIFY_SSL=false` est toléré **uniquement en développement
  local**, jamais commité, jamais déployé.

Signaler une vulnérabilité en privé à l'équipe, avant publication d'un ticket.

---

## 9. Points ouverts à trancher

Ces questions sont ouvertes et une décision les débloque. N'en réglez pas
une vous-même sans discussion :

1. **Bruit d'outils** : le CDC dit 9, en liste 10, le code en expose 8.
   B4/B5 sont écrits mais non enregistrés : les publier, ou les retirer du
   périmètre de la phase 1 ?
2. **Entité `dataservice`** : le portail n'en a pas. Que vaut
   `dataservice_id` pour B4/B5 — un dataset, une ressource ?
3. **B5/OpenAPI** : le catalogue ne publie aucune spécification. Extraire à la
   volée, ou retirer l'outil du périmètre ?
4. **C1 et SQL** : en direct, `eq`, `in` et `contains` répondent, mais `gt` et
   `lt` provoquent une erreur HTTP 500 du portail. On garde la comparaison
   documentée comme « peu fiable », ou on bascule sur `datastore_search_sql`
   (⇒ `WHERE` construit, `total` exact perdu) ?
5. **C2 et `.xls`** : la lecture CSV est vérifiée en direct ; un vrai `.xls`
   échoue (`XLRDError`). Faut-il ajouter la dépendance `xlrd`, ou annonce-t-on
   CSV/JSON/GeoJSON uniquement ?
6. **C3** : le portail n'expose que `downloads_count`. Que faire de *vues*,
   *réutilisations* et *tendance* ? Faut-il retirer `period` de la signature,
   puisqu'il est décoratif aujourd'hui ?
7. **B2 sans pagination** : l'outil n'expose que `dataset_id`, alors que le CDC
   prévoit `page`/`page_size`. Est-ce un oubli ou une décision ?
8. **Sentry / Matomo / rate limiting** : activés en prod malgré le code
   non fonctionnel, ou bloqués jusqu'à implémentation ? (CORS et `ALLOWED_HOSTS`
   sont désormais appliqués : ce n'est plus une question ouverte.)
9. **Format de sortie** : texte brut (actuel) ou JSON structuré ? La famille C
   est en production ; la décision structurante arrive tard.

---

## 10. Licence

MIT. **Le fichier `LICENSE` ne contient pour l'instant qu'un commentaire
d'en-tête** : le texte de la licence doit être ajouté (Décret 2021-3 art. 14,
exigez une publication Open Source vérifiable).

En contribuant, vous acceptez que votre contribution soit publiée sous MIT.
