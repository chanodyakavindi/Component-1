from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[4]
CONTRACTS = Path("/contracts") if Path("/contracts").exists() else ROOT / "packages" / "contracts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(ROOT / ".env"), ".env"), extra="ignore")

    app_env: str = "development"
    app_name: str = "Child Nutrition Intelligence Platform"
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    inference_url: str = "http://localhost:8001"

    database_url: str = "postgresql+psycopg://cnip:cnip_dev_password@localhost:5432/cnip"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-access-secret-dev-only"
    jwt_refresh_secret: str = "change-me-refresh-secret-dev-only"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    encryption_key: str = "change-me-32-byte-fernet-or-hex-dev"

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    model_mode: str = "demo"
    model_artifact_path: str = "/artifacts/active"
    embedding_dim: int = 128

    notification_provider: str = "mock"
    sms_api_key: str = ""
    email_api_key: str = ""

    fhir_enabled: bool = False
    fhir_base_url: str = ""
    fhir_version: str = "R4"
    hospital_adapter: str = "mock"

    c2_explainability_url: str = ""
    c3_counterfactual_url: str = ""
    c4_drift_url: str = ""
    integration_mode: str = "mock"

    log_level: str = "INFO"
    log_json: bool = True
    seed_on_start: bool = False

    contracts_dir: Path = CONTRACTS
    failed_login_limit: int = 8
    lockout_minutes: int = 15

    @property
    def access_ttl(self) -> timedelta:
        return timedelta(minutes=self.jwt_access_minutes)

    @property
    def refresh_ttl(self) -> timedelta:
        return timedelta(days=self.jwt_refresh_days)

    @property
    def is_dev(self) -> bool:
        return self.app_env in {"development", "dev", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
