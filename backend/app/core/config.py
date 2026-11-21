"""Configuration par variables d'environnement (préfixe ``PAIE_``).

Les secrets ne sont jamais journalisés : ``secret_key`` et le mot de passe de ``db_url``
sont des ``SecretStr`` et ne s'affichent pas dans ``repr``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAIE_", env_file=None, extra="ignore")

    env: str = "dev"
    db_url: SecretStr | None = None          # ex. mysql+pymysql://paie_app:***@paie-db:3306/paie
    secret_key: SecretStr | None = None
    seed_demo: bool = False
    log_level: str = "INFO"
    db_pool_recycle: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
