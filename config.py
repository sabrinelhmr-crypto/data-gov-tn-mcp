"""
Configuration du serveur MCP data.gov.tn.
Charge les variables d'environnement définies dans .env (voir section 5.2 du CDC).
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Serveur MCP ---
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000
    MCP_ENV: Literal["local", "preprod", "prod", "demo"] = "local"

    # --- API data.gov.tn ---
    DATAGOV_API_ENV: Literal["prod", "demo"] = "prod"
    DATAGOV_API_BASE_URL: str = "https://catalog.data.gov.tn/api/3"
    DATAGOV_API_KEY: str | None = None
    # Verification TLS. Desactiver (false) uniquement si le store CA local est
    # incomplet (typique des environnements de developpement / proxy d'entreprise).
    DATAGOV_API_VERIFY_SSL: bool = True

    # --- Logging ---
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- Monitoring ---
    SENTRY_DSN: str | None = None
    SENTRY_SAMPLE_RATE: float = 1.0
    MATOMO_URL: str | None = None
    MATOMO_SITE_ID: str | None = None

    # --- Sécurité ---
    ALLOWED_HOSTS: str = "data.gov.tn,www.data.gov.tn,catalog.data.gov.tn,mcp.data.gov.tn"
    ALLOWED_ORIGINS: str = "*"
    CORS_ENABLED: bool = True

    # --- Performance ---
    MAX_PAGE_SIZE: int = 100
    MAX_DOWNLOAD_SIZE_MB: int = 100
    REQUEST_TIMEOUT: int = 30
    # Nombre total de tentatives sur l'API data.gov.tn (1 = pas de retry).
    # Le retry ne s'applique qu'aux erreurs transitoires : timeout, erreur
    # reseau, et statuts 429/502/503/504. Un 4xx definitive n'est pas rejoue.
    API_MAX_ATTEMPTS: int = 3
    # Delai avant le premier retry, en secondes ; double a chaque essai.
    API_RETRY_BACKOFF: float = 0.25
    # Plafond du delai de retry, en secondes (le backoff ne depasse pas).
    API_RETRY_BACKOFF_MAX: float = 2.0

    # --- Rate limiting (CDC 6.1 : 100 requetes/minute/IP) ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 100
    # Requetes tolerees au-dela du quota dans la fenetre, avant retour 429.
    RATE_LIMIT_BURST: int = 20
    # Les probes /health sont exclues du quota : elles viennent de
    # l'orchestrateur, pas d'un utilisateur, et ne doivent pas consommer
    # le budget des clients reels.
    RATE_LIMIT_EXEMPT_PATHS: str = "/health,/health/ready"
    # L'IP cliente est celle du socket sauf si le reverse proxy est declare
    # de confiance. Sans cette declaration, lire X-Forwarded-For permettrait a
    # n'importe qui de forger une IP et de contourner le quota.
    RATE_LIMIT_TRUST_PROXY: bool = False
    # Adresses (ou motifs, ex: "10.0.0.0/8" non gere : utilisez "*" ou un
    # suffixe ".example.org") des proxys dont le X-Forwarded-For fait foi.
    # Indispensable : sans liste, TRUST_PROXY reste inoperant et le quota
    # s'applique au proxy lui-meme, donc a tous les clients confondus.
    RATE_LIMIT_TRUSTED_PROXIES: str = "127.0.0.1,::1"
    # Nombre maximum d'IP memorisees en meme temps (garde-fou memoire).
    RATE_LIMIT_MAX_KEYS: int = 10_000

    # --- Telchargement de ressources (C2) ---
    # Hotes autorises pour le telechargement des fichiers de ressources.
    # Vide = tout hote public est accepte, ce qui est le cas reel aujourd'hui :
    # les fichiers du portail sont heberges sur catalog.agridata.tn et
    # d'autres domaines gouvernementaux, pas sur data.gov.tn.
    # Renseigner une liste (ex: "*.data.gov.tn,catalog.agridata.tn") resserre
    # la surface d'atteinte. Le garde-fou bloque de toute facon les adresses
    # privees, loopback, link-local et multicast.
    DOWNLOAD_ALLOWED_HOSTS: str = ""

    @property
    def download_allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.DOWNLOAD_ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def rate_limit_exempt_paths_list(self) -> list[str]:
        return [p.strip() for p in self.RATE_LIMIT_EXEMPT_PATHS.split(",") if p.strip()]

    @property
    def rate_limit_trusted_proxies_list(self) -> list[str]:
        return [p.strip() for p in self.RATE_LIMIT_TRUSTED_PROXIES.split(",") if p.strip()]


# Instance unique importable partout : from config import settings
settings = Settings()
