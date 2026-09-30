# Guide de déploiement — Serveur MCP data.gov.tn

<div dir="rtl">

# دليل النشر — خادم بيانات تونس المفتوحة

</div>

# Deployment guide — data.gov.tn MCP server

Guide de mise en production du serveur MCP : construction de l'image Docker,
exécution du conteneur, durcissement réseau et exploitation quotidienne.

**Résumé EN** — Production deployment guide for the data.gov.tn MCP server:
building the image, running the container, TLS termination, health checks and
operations.

Portée : déploiement en production d'un **MVP expérimental** (CDC §1.2). Les
sprints 2 à 6 (outils B/C, CI/CD, monitoring) ne sont pas terminés — voir
[docs/api_reference.md](api_reference.md).

---

## 1. Prérequis

| Élément | Exigence |
|---------|----------|
| Docker Engine | 24+ |
| Docker Compose | v2 (`docker compose`, pas `docker-compose`) |
| Accès au portail | `https://catalog.data.gov.tn/api/3` joignable en sortie |
| Certificat TLS | Pour `mcp.data.gov.tn` (Let's Encrypt) |

Vérification :

```bash
docker --version
docker compose version
curl -sS -o /dev/null -w '%{http_code}\n' https://catalog.data.gov.tn/api/3/action/status_show
```

> ⚠️ **L'URL du CDC est périmée.** Le CDC §5.2 indique
> `https://www.data.gov.tn/api/3` (qui renvoie `404`). L'API réellement en
> service est sur `https://catalog.data.gov.tn/api/3`. Utilisez cette dernière.

---

## 2. Construction de l'image

```bash
# Build simple
docker build -t datagov-mcp-tn:0.1.0 .

# Build avec tag de version, multi-plateforme si nécessaire
docker build -t registry.example.tn/datagov-mcp-tn:0.1.0 .
docker push registry.example.tn/datagov-mcp-tn:0.1.0
```

Le `Dockerfile` actuel :

```dockerfile
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
COPY README.md .
RUN pip install --no-cache-dir .
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

À savoir :

- `curl` est installé **exclusivement** pour le healthcheck du Compose.
- Le build copie le code **avant** `pip install` (`COPY . .` puis
  `RUN pip install .`). C'est obligatoire ici : `pyproject.toml` force
  l'inclusion de `main.py`, `config.py` et `logging_config.py`, et le build
  échoue avec `Forced include not found` si le code est absent. Conséquence :
  le cache des couches de dépendances est moins efficace qu'un build en deux
  étapes.
- **Le conteneur tourne en utilisateur non privilégié** : `USER mcp`
  (uid 10001, sans shell ni home). Le service n'écrit rien sur disque, donc
  aucune élévation n'est nécessaire.

- Le CDC §9.3 exige « zéro vulnérabilité critique » (Snyk/Trivy). Ajoutez un
  scan au pipeline CI ; ce n'est pas encore en place.

---

## 3. Exécution avec Docker Compose

Le `docker-compose.yml` fourni publie `${MCP_PORT:-8000}:8000` et déclare un
healthcheck sur `/health/ready`.

```bash
# Valeurs par défaut
docker compose up -d --build

# Personnalisé
MCP_PORT=8007 MCP_ENV=prod LOG_LEVEL=INFO docker compose up -d

# Vie du service
docker compose ps
docker compose logs -f mcp-server
docker compose down
```

> ⚠️ **Le healthcheck est strict.** Il teste `/health/ready`, qui renvoie `503`
> dès que l'API `data.gov.tn` est injoignable. Le conteneur sera donc marqué
> `unhealthy` lors d'une panne en aval — c'est voulu, mais cela implique que
> **le restart policy et le load balancer doivent tolérer cette situation**.
> Utilisez `/health` pour la liveness si vous préférez découpler les deux.

### Variables à définir en production

Le Compose ne transmet que 6 variables. Ajoutez celles qui manquent :

```yaml
services:
  mcp-server:
    build: .
    ports:
      - "127.0.0.1:8000:8000"     # ⚠️ ne pas exposer 0.0.0.0 en production
    environment:
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - MCP_ENV=prod
      - DATAGOV_API_ENV=prod
      - DATAGOV_API_BASE_URL=https://catalog.data.gov.tn/api/3
      - DATAGOV_API_VERIFY_SSL=true
      - LOG_LEVEL=INFO
      - REQUEST_TIMEOUT=30
      - MAX_PAGE_SIZE=100
      - MAX_DOWNLOAD_SIZE_MB=100
      # Secrets : via --env-file ou un gestionnaire, jamais en clair
      - SENTRY_DSN=${SENTRY_DSN:-}
      - SENTRY_SAMPLE_RATE=0.1
      - MATOMO_URL=${MATOMO_URL:-}
      - MATOMO_SITE_ID=${MATOMO_SITE_ID:-}
    env_file:
      - .env.production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
```

Changements recommandés par rapport au fichier fourni :

| Changement | Pourquoi |
|------------|----------|
| `ports: 127.0.0.1:8000:8000` | Le port ne doit pas être publiquement joignable ; le reverse proxy est le seul point d'entrée. |
| `SENTRY_SAMPLE_RATE=0.1` | `1.0` en prod est coûteux ; le taux est configurable (CDC §7.2). |
| `logging.options` | Empêche `.json` de saturer le disque. |

> ⚠️ **Variables non fonctionnelles.** `SENTRY_DSN` et `MATOMO_URL` sont
> transmises au conteneur mais **ne produisent aucun événement** :
> `sentry-sdk` n'est pas une dépendance et n'est jamais initialisé, et
> `helpers/matomo.py` est vide. Le CDC §7.2–7.3 les exige ; c'est une dette
> connue, à traiter avant d'activer ces variables en prod.
>
> ✅ **CORS / `ALLOWED_HOSTS` appliqués.** `main.py` construit l'application
> avec `host_origin_protection=True` **et** `allowed_hosts` / `allowed_origins`.
> Le `True` est indispensable : sans lui FastMCP reçoit les listes mais
> n'installe pas le middleware de vérification (défaut `False`). Conséquences :
> un `Host` hors liste reçoit **421**, une origine tierce reçoit **403**. La
> défense en profondeur reste recommandée côté reverse proxy (section 4).

> ⚠️ **Le rate limiting reste absent** (CDC §6.1 : 100 req/min/IP) : à faire
> au reverse proxy, section 6.

---

## 4. Reverse proxy et TLS

Cible : `https://mcp.data.gov.tn/mcp`.

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.data.gov.tn;

    ssl_certificate     /etc/letsencrypt/live/mcp.data.gov.tn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.data.gov.tn/privkey.pem;

    # Défense en profondeur : ALLOWED_HOSTS est aussi appliqué par l'application
    # (421 sur Host inconnu), mais un proxy explicite vaut mieux qu'une erreur.
    if ($host !~ ^(mcp|data|www|catalog)\.data\.gov\.tn$) {
        return 444;
    }

    # --- Sonde de santé, hors journal d'accès ---
    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
    location = /health/ready {
        proxy_pass http://127.0.0.1:8000/health/ready;
        access_log off;
    }

    # --- Endpoint MCP ---
    location /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_http_version 1.1;

        # Streamable HTTP : indispensable de ne pas tamponner
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering     off;
        proxy_cache         off;
        proxy_read_timeout  120s;
        proxy_send_timeout  120s;
    }

    # Tout le reste est refusé
    location / { return 404; }
}

server {
    listen 80;
    server_name mcp.data.gov.tn;
    return 301 https://$host$request_uri;
}
```

Points critiques :

- **`proxy_buffering off`** est obligatoire : la désactivation de la mise en
  tampon évite que les réponses JSON-RPC en flux ne restent bloquées en tampon
  chez Nginx.
- **`proxy_http_version 1.1`** et un `Connection` cohérent sont requis pour le
  transport Streamable HTTP.
- `proxy_read_timeout` relevé à 120 s : l'outil C2 (analyse de fichiers) peut
  être long. Le CDC propose 60 s, ce qui est serré.

### CORS

Le middleware `HostOriginGuardMiddleware` de FastMCP **applique**
`ALLOWED_ORIGINS` : une origine qui n'y figure pas reçoit **403** avant tout
traitement. `ALLOWED_ORIGINS=*` est refusé au démarrage quand `MCP_ENV=prod`,
et `CORS_ENABLED=false` renvoie une liste vide, ce qui bloque toute origine
étrangère (les clients MCP non navigateur n'envoient pas d'`Origin` et
passent). Un client qui appelle le serveur depuis une même origine reste
autorisé.

L'application n'émet toujours **pas** d'en-tête CORS (pas de
`Access-Control-Allow-Origin`). Si un client navigateur en a besoin,
ajoutez-le ici :

```nginx
add_header Access-Control-Allow-Origin  "https://votre-client.example" always;
add_header Access-Control-Allow-Methods "POST, GET, OPTIONS" always;
add_header Access-Control-Allow-Headers "Content-Type, Accept, Mcp-Session-Id" always;
```

Restreignez `Allow-Origin` à une liste blanche : `ALLOWED_ORIGINS=*` en
production est un risque (CDC §5.2 le signale explicitement) et l'application
refuse de démarrer dans ce cas.

### Limitation de débit (rate limiting)

Le CDC §6.1 demande 100 requêtes/minute/IP. **Non implémenté côté
application.** À faire au niveau Nginx :

```nginx
location /mcp {
    limit_req zone=mcp burst=20 nodelay;
    limit_req_status 429;
    # ... proxy_pass ...
}
```

avec, dans le bloc `http` :

```nginx
limit_req_zone $binary_remote_addr zone=mcp:10m rate=100r/m;
```

---

## 5. Kubernetes (optionnel)

Le CDC §8.3 prévoit Kubernetes pour la scalabilité. Manifeste minimal :

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: datagov-mcp-tn
spec:
  replicas: 2
  selector:
    matchLabels: { app: datagov-mcp-tn }
  template:
    metadata:
      labels: { app: datagov-mcp-tn }
    spec:
      containers:
        - name: mcp
          image: registry.example.tn/datagov-mcp-tn:0.1.0
          ports: [{ containerPort: 8000 }]
          env:
            - { name: MCP_ENV, value: "prod" }
            - { name: DATAGOV_API_ENV, value: "prod" }
            - { name: DATAGOV_API_BASE_URL, value: "https://catalog.data.gov.tn/api/3" }
            - { name: DATAGOV_API_VERIFY_SSL, value: "true" }
            - { name: LOG_LEVEL, value: "INFO" }
          livenessProbe:
            httpGet: { path: /health, port: 8000 }
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet: { path: /health/ready, port: 8000 }
            initialDelaySeconds: 15
            periodSeconds: 30
          resources:
            requests: { cpu: 100m, memory: 256Mi }
            limits:   { memory: 1Gi }
---
apiVersion: v1
kind: Service
metadata:
  name: datagov-mcp-tn
spec:
  selector: { app: datagov-mcp-tn }
  ports: [{ port: 80, targetPort: 8000 }]
```

> Utilisez `/health` pour la **liveness** et `/health/ready` pour la
> **readiness** : à l'inverse du healthcheck Compose, une panne de l'API
> `data.gov.tn` ne doit pas provoquer un redémarrage en boucle des pods.

Limites de ressources : `pandas` (outil C2) consomme beaucoup de mémoire.
`1Gi` est un plancher ; ajustez selon `MAX_DOWNLOAD_SIZE_MB`.

---

## 6. Exploitation

### Vérifier le déploiement

```bash
curl -s https://mcp.data.gov.tn/health      | jq .
curl -s https://mcp.data.gov.tn/health/ready | jq .
```

`/health` doit renvoyer `"status": "healthy"` et `"tools_count": 8`.
Si `tools_count` vaut `0`, `tools/__init__.py` n'enregistre rien — vérifiez que
votre image contient bien le code à jour. Toute valeur inférieure à 8 signifie
qu'un `add_tool()` manque dans `tools/__init__.py` : l'outil est invisible des
clients même si le fichier est présent.

Tester un appel réel d'outil :

```bash
curl -sS -X POST https://mcp.data.gov.tn/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"search_datasets",
                 "arguments":{"query":"eau potable","page_size":2}}}'
```

### Logs

Les logs sont **JSON sur `stdout`** (`logging_config.py`, `python-json-logger`),
avec les champs `asctime`, `levelname`, `name`, `message`. Ils sont directement
exploitables par Loki ou Elasticsearch.

> Le CDC §7.4 demande des champs supplémentaires (`tool_name`, `duration`,
> `error_type`, `request_id`) : **ils ne sont pas encore émis.** À instrumenter.

Collecte :

```bash
docker compose logs -f mcp-server | jq -c .
docker compose logs --since 1h --tail 500 mcp-server > /tmp/mcp.log
```

### Mise à jour

```bash
git pull
docker compose build --pull
docker compose up -d
docker compose ps          # attendre 'healthy'
curl -s localhost:8000/health | jq .tools_count
```

### Rollback

```bash
docker tag registry.example.tn/datagov-mcp-tn:0.1.0 registry.example.tn/datagov-mcp-tn:rollback
# puis re-taguer la versionStable et redémarrer
```

---

## 7. Sécurité et conformité — points bloquants

Avant une exposition publique, ces éléments sont à traiter. Ils sont listés
ici pour être honnête sur l'état réel, pas pour être décoratifs.

| Exigence | État | Action requise |
|----------|------|----------------|
| Rate limiting 100 req/min/IP (CDC §6.1) | ❌ Absent | Nginx `limit_req` |
| CORS / `ALLOWED_HOSTS` (CDC §6.1) | ✅ Appliqué (`host_origin_protection=True`, 421/403) | Garder `ALLOWED_ORIGINS` explicite en prod |
| Conteneur non-root | ✅ `USER mcp` (uid 10001) | — |
| Limitation payload 1 Mo (CDC §6.1) | ❌ Absent | `client_max_body_size` Nginx |
| Sentry (CDC §7.2) | ❌ Non initialisé | Ajouter `sentry-sdk` + `init()` |
| Matomo anonymisé (CDC §7.3) | ❌ `matomo.py` vide | Implémenter |
| Métadonnées trilingues (Décret 2021-3 art. 16) | ⚠️ `lang` FR/EN/AR sur B1–B5, libellés seuls | Étendre aux familles A et C |
| Licence MIT (art. 14) | ❌ `LICENSE` vide | Écrire le texte de la licence |
| Téléchargement C2 borné (CDC §6.1) | ✅ Flux.stream() + `max_bytes`, coupe en cours de lecture | — |
| Téléchargement C2 anti-SSRF (CDC §6.1) | ✅ Schéma/Hôte/IP publique contrôlés à chaque redirection | Restreindre `DOWNLOAD_ALLOWED_HOSTS` en prod |
| Validation Pydantic des entrées | ✅ `strict_input_validation=True` + masquage des erreurs en prod | — |
| Échappement des filtres côté portail | ✅ C1 livré (filtres transmis en JSON à `datastore_search`) | Voir la limite ci-dessous |
| Pas de données personnelles stockées (RGPD) | ✅ Aucun stockage | — |
| TLS vérifié vers data.gov.tn | ✅ `VERIFY_SSL=true` | Ne pas désactiver |

Points d'attention :

- **Le serveur est public et sans authentification** (Décret 2021-3 art. 9).
  C'est voulu, mais cela rend le rate limiting non négociable : sans lui, le
  portail `data.gov.tn` peut être saturé par un tiers via votre serveur.
- **C1 n'exécute pas de SQL construit par l'outil.** Les filtres sont envoyés
  comme objet JSON à `datastore_search`, donc l'échappement est confié au
  portail. Vérifié en direct : `eq`, `in` et `contains` fonctionnent, mais
  `gt` et `lt` provoquent une erreur **HTTP 500 du portail**. Ne basculez pas
  vers `datastore_search_sql` de votre propre initiative : le `total` exact est
  alors perdu.
- **C2 ne lit pas les vrais `.xls`.** Le format est accepté, mais la lecture
  échoue (`XLRDError`) : `xlrd` n'est pas une dépendance. Testez avec du
  CSV/JSON avant d'annoncer la couverture de formats.
- **`DATAGOV_API_VERIFY_SSL=false` ne doit jamais être déployé.** Enveloppez la
  variable dans une garde de CI si vous devez la garder configurable.
- **Aucune clé API n'est requise**, donc rien à faire tourner. Si `DATAGOV_API_KEY`
  est renseignée, elle est envoyée en en-tête `Authorization` — ne la commitez
  jamais (`.env` est dans `.gitignore`, ce qui est correct).

---

## 8. Checklist de mise en production

- [ ] `LICENSE` complété avec le texte MIT
- [ ] Image construite et poussée dans un registre privé
- [ ] Conteneur non-root ✅ fait (`USER mcp`)
- [ ] `.env.production` hors du dépôt, permissions `600`
- [ ] `MCP_ENV=prod`, `DATAGOV_API_ENV=prod`, `DATAGOV_API_VERIFY_SSL=true`
- [ ] Port 8000 non exposé publiquement
- [ ] Nginx : TLS, contrôle `Host`, `proxy_buffering off`, timeouts 120 s
- [ ] Rate limiting configuré
- [ ] `client_max_body_size` limité à 1 Mo
- [ ] `/health` et `/health/ready` sondés par le superviseur
- [ ] Rotation des logs configurée
- [ ] Sauvegarde : *aucune donnée à sauvegarder* (le serveur est sans état)
- [ ] Scan de vulnérabilités de l'image passé (Snyk/Trivy)
- [ ] Documentation à jour ([api_reference.md](api_reference.md))
- [ ] Revue conformité Décret 2021-3 par l'Unité Admin Électronique (CDC §9.3)
