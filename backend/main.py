"""
main.py — SubTerra
FastAPI application entry point.
Registers all routes, middleware, startup events.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from api.main import router
from db.database import check_connection, init_db

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("subterra.main")


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks, then yield, then cleanup on shutdown."""
    log.info("=" * 55)
    log.info(f"  Starting {settings.APP_NAME} ({settings.APP_ENV})")
    log.info("=" * 55)

    # Initialise DB schema + TimescaleDB hypertable on first startup
    try:
        init_db()
        log.info("  Database: schema ready ✓")
    except Exception as e:
        log.error(f"  Database: init failed — {e}")
        log.error("  Check DATABASE_URL and that the db container is healthy")

    # Quick connectivity ping
    if check_connection():
        log.info("  Database: connected ✓")
    else:
        log.error("  Database: UNREACHABLE — routes will fail until DB is up")

    yield

    log.info(f"  {settings.APP_NAME} API shutting down.")


# ── App Factory ────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = settings.APP_NAME,
    description = (
        "Real-Time Groundwater Resource Evaluation Platform. "
        "Analyses 5,260 DWLR stations across India using live CGWB sensor data."
    ),
    version     = settings.API_VERSION,
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)


# ── CORS — uses ALLOWED_ORIGINS from config ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,   # ["http://localhost:3000", ...]
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api")


# ── Root ───────────────────────────────────────────────────────────────────────
@app.get("/", tags=["System"])
def root():
    return {
        "service":     settings.APP_NAME,
        "version":     settings.API_VERSION,
        "status":      "running",
        "docs":        "/docs",
        "description": "Real-Time Groundwater Evaluation — CGWB Problem Statement #25068",
    }