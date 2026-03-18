"""
SubTerra — App Configuration
backend/config.py
Loads all settings from environment variables / .env file.
Never hardcode secrets — always use this file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── App ──────────────────────────────────────────────────────────────
    APP_NAME:    str  = "SubTerra"
    APP_VERSION: str  = "1.0.0"
    APP_ENV:     str  = "development"   # development | production | test
    DEBUG:       bool = True
    SECRET_KEY:  str  = "change-this-in-production"
    API_VERSION: str  = "v1"

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://subterra_user:subterra_pass@localhost:5432/subterra"

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL:            str = "redis://localhost:6379"
    CACHE_EXPIRE_SECONDS: int = 3600    # your field name — cache API responses 1 hour
    CACHE_TTL_SEC:        int = 300     # shorter TTL used by service layer

    # ── Data Sources ──────────────────────────────────────────────────────
    INDIA_WRIS_BASE_URL: str = "https://indiawris.gov.in"
    WRIS_BASE_URL:       str = "https://indiawris.gov.in/wris"   # GeoServer endpoint
    IMD_BASE_URL:        str = "https://imdaws.imd.gov.in"       # corrected IMD AWS URL
    DATA_GOV_API_KEY:    str = ""       # optional — register at data.gov.in

    # ── Data Refresh ──────────────────────────────────────────────────────
    DATA_REFRESH_INTERVAL: int = 21600  # your field — 6h for scheduler
    FETCH_INTERVAL_SEC:    int = 900    # scraper field — 15 min (matches DWLR sensor rate)
    MAX_RETRIES:           int = 3
    RETRY_BACKOFF_SEC:     int = 10
    REQUEST_TIMEOUT_SEC:   int = 30

    # ── Algorithm Defaults ────────────────────────────────────────────────
    TASK1_DEFAULT_HOURS:  int = 168     # 7 days of readings for Task 1
    TASK2_DEFAULT_DAYS:   int = 365     # 1 year for monsoon comparison in Task 2
    TASK3_DEFAULT_DAYS:   int = 365     # 1 year for depletion trend in Task 3
    ALERT_LOOKBACK_HOURS: int = 48      # how far back alerts scan

    # ── CORS ──────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",    # React dev server (CRA)
        "http://localhost:5173",    # Vite dev server
    ]

    class Config:
        env_file       = ".env"
        case_sensitive = True
        extra          = "ignore"   # silently ignore unknown env vars


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Use as FastAPI dependency: Depends(get_settings)
    Or direct import: from app.config import settings
    """
    return Settings()


# Convenience singleton for direct imports
settings = get_settings()
