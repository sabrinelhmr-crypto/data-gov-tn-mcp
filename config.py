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

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


# Instance unique importable partout : from config import settings
settings = Settings()
