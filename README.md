# data-gov-tn-mcp

Serveur **MCP** (Model Context Protocol) pour le portail Open Data de la Tunisie
([data.gov.tn](https://catalog.data.gov.tn/fr/dataset)). Lecture seule (Phase 1).

Le serveur expose des *outils* que vos assistants IA (Claude Desktop, etc.)
peuvent appeler pour rechercher et consulter les données publiques tunisiennes.

## Prérequis

- **Python 3.13** ou supérieur
- **Git**
- **Docker** (optionnel, seulement si vous voulez le mode conteneurisé)

## Démarrage rapide

```bash
# 1. Récupérer le projet
git clone https://github.com/sabrinelhmr-crypto/data-gov-tn-mcp.git
cd data-gov-tn-mcp

# 2. Créer l'environnement virtuel puis l'activer
python -m venv venv

# Windows :
venv\Scripts\activate
# Linux / macOS :
# source venv/bin/activate

# 3. Installer les dépendances
pip install -e ".[dev]"

# 4. Lancer le serveur
python main.py
```

⚠️ L'API de `data.gov.tn` est publique : **aucune configuration n'est nécessaire**
pour démarrer. Les réglages optionnels (clé API, monitoring) se font dans `.env`
(voir `.env.example`).

## Vérifier que ça marche

Dans un autre terminal :

```bash
curl http://localhost:8000/health
```

Réponse attendue : `{"status": "healthy", "tools_count": 2, ...}`

Le serveur MCP est accessible sur `http://localhost:8000/mcp`.

## Lancer les tests

```bash
python -m pytest
```

La commande exécute tous les tests et affiche la couverture de code
(minimum requis : **90 %**).

## Les outils disponibles

| # | Outil | Description | État |
|---|-------|-------------|------|
| A1 | `search_datasets` | Recherche de jeux de données par mots-clés | ✅ |
| A2 | `get_dataset_info` | Métadonnées détaillées d'un jeu de données | ✅ |
| A3 | `list_dataset_resources` | Liste des ressources d'un jeu de données | 🔜 |
| A4 | `download_and_parse_resource` | Télécharge et parse une ressource (CSV, Excel...) | 🔜 |
| A5 | `get_dataservice_info` | Infos d'un service de données | 🔜 |
| A6 | `get_dataservice_openapi_spec` | Spécification OpenAPI d'un service | 🔜 |
| A7 | `get_resource_info` | Infos d'une ressource | 🔜 |
| A8 | `query_resource_data` | Interroge les données d'une ressource | 🔜 |
| B1 | `search_dataservices` | Recherche de services de données | 🔜 |
| B2 | `get_metrics` | Statistiques du portail | 🔜 |

## Structure du projet

```
├── main.py                  # Point d'entrée (serveur + health check)
├── config.py                # Configuration (via .env)
├── tools/                   # Les outils MCP (un fichier par outil)
├── helpers/                 # Code partagé (client API, nettoyage requêtes...)
├── models/                  # Modèles de données (Phase 2)
├── tests/                   # Tests unitaires
└── docs/                    # Documentation
```

## Utilisation avec Claude Desktop

Ajoutez cette configuration à votre `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "data.gov.tn": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Déploiement Docker (optionnel)

```bash
docker compose up -d --build
curl http://localhost:8000/health/ready
```

## Licence

MIT — voir le fichier [LICENSE](LICENSE).
