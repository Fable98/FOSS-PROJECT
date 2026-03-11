"""
SubTerra — App Configuration
backend/app/config.py

Loads all settings from environment variables / .env file.
Never hardcode secrets — always use this file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────
    APP_NAME: str        = "SubTerra"
    APP_VERSION: str     = "1.0.0"
    APP_ENV: str         = "development"       # development | production | test
    DEBUG: bool          = True
    SECRET_KEY: str      = "change-this-in-production"

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str    = "postgresql://subterra_user:subterra_pass@localhost:5432/subterra"

    # ── Redis ────────────────────────────────────────────────
    REDIS_URL: str       = "redis://localhost:6379"
    CACHE_EXPIRE_SECONDS: int = 3600           # Cache API responses for 1 hour

    # ── Data Sources ─────────────────────────────────────────
    INDIA_WRIS_BASE_URL: str = "https://indiawris.gov.in"
    IMD_BASE_URL: str        = "https://imd.gov.in"
    DATA_GOV_API_KEY: str    = ""              # Optional — from data.gov.in

    # ── Data Refresh ─────────────────────────────────────────
    DATA_REFRESH_INTERVAL: int = 21600         # 6 hours in seconds

    # ── CORS ─────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",               # React dev server
        "http://localhost:5173",               # Vite dev server
    ]

    class Config:
        env_file = ".env"                      # Load from .env file
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Use this everywhere instead of creating new Settings().
    """
    return Settings()
