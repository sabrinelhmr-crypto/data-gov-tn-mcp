# data-gov-tn-mcp

MCP server for Tunisia's Open Data portal (data.gov.tn).
Read-only, Phase 1. See `docs/architecture.md` for details.

## Prérequis-
 Python 3.12 ou supérieur
 - Docker et Docker Compose (optionnel, pour le déploiement conteneurisé)
 - Git

## Installation
```bash
git clone https://github.com/<ton-compte>/data-gov-tn-mcp.git
cd data-gov-tn-mcp
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
```

## Configuration
```bash
copy .env.example .env
```
Édite le fichier `.env` selon ton environnement (voir la liste des variables dans `.env.example`).


## Lancement
En local :
```bash
python main.py
```
Avec Docker :
```bash
docker compose up -d --build
```
Vérifier que le serveur tourne :
```bash
curl http://localhost:8000/health
```

## Utilisation avec Claude Desktop
```json
{
  "mcpServers": {
    "data.gov.tn": {
      "url": "http://localhost:8000/mcp",
      "transport": "http"
    }
  }
}
```

## Licence
MIT — voir le fichier LICENSE.
