"""
SubTerra — Database Connection & Session Management
backend/app/db/database.py

Architecture:
  - Sync SQLAlchemy engine + session → used by all FastAPI routes and services
  - Async init_db() → called once at app startup (lifespan)
  - check_db_connection() → sync, used by /health endpoint

Why sync (not async)?
  The full pipeline (scraper → clean_data → db_writer) is synchronous psycopg2.
  All three Phase 2 service files (analytics, recharge, alerts) are sync.
  Mixing one async DB layer into a sync stack causes generator/await conflicts.
  Sync SQLAlchemy is simpler, equally performant for this use case, and consistent.

Both the pipeline (psycopg2 direct writes) and FastAPI routes (SQLAlchemy reads)
talk to the same three tables defined in app/models/station.py:
  - stations
  - dwlr_readings
  - rainfall
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings                 # backend/config.py
from app.models.station import Base         # Station, DWLRReading, Rainfall

log = logging.getLogger("subterra.database")


# ─────────────────────────────────────────────
# ENGINE — sync, connection pooled
# ─────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,                  # postgresql://user:pass@db:5432/subterra
    echo=settings.DEBUG,                    # logs every SQL query when DEBUG=True
    pool_size=10,                           # keep 10 connections open
    max_overflow=20,                        # allow 20 extra under heavy load
    pool_pre_ping=True,                     # verify connection alive before use
    pool_recycle=3600,                      # recycle connections every hour
)


# ─────────────────────────────────────────────
# SESSION FACTORY
# One session per request — never share sessions across requests.
# ─────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,                 # keep objects usable after commit
)


# ─────────────────────────────────────────────
# DEPENDENCY — injected into every FastAPI route
# ─────────────────────────────────────────────
def get_db():
    """
    FastAPI dependency — provides a DB session per request.
    Commits on success, rolls back on any exception,
    always closes the session when the request is done.

    Usage in any route:
        from sqlalchemy.orm import Session
        from fastapi import Depends
        from app.db.database import get_db

        @router.get("/something")
        def my_route(db: Session = Depends(get_db)):
            return db.query(Station).all()
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────
# INIT — called once at startup from main.py lifespan
# Kept as a regular function (not async) — engine.begin() is sync.
# main.py calls it inside the lifespan context manager.
# ─────────────────────────────────────────────
def init_db():
    """
    Creates all three tables if they don't already exist:
      - stations       (from Station model)
      - dwlr_readings  (from DWLRReading model)
      - rainfall       (from Rainfall model)

    Also enables TimescaleDB hypertable on dwlr_readings
    for fast 7-day chunk time-series queries.
    Falls back silently if TimescaleDB is not available.

    Safe to call multiple times — all DDL uses IF NOT EXISTS.
    db_writer.py also calls ensure_schema() via psycopg2 on pipeline
    startup — both are idempotent, no conflict.
    """
    with engine.begin() as conn:

        # Create all tables from station.py models
        Base.metadata.create_all(conn)
        log.info("  Tables created (stations, dwlr_readings, rainfall) ✅")

        # TimescaleDB hypertable — 7-day chunks on dwlr_readings
        # Makes "last 30 days for station X" queries extremely fast
        try:
            conn.execute(text("""
                SELECT create_hypertable(
                    'dwlr_readings',
                    'timestamp',
                    if_not_exists       => TRUE,
                    migrate_data        => TRUE,
                    chunk_time_interval => INTERVAL '7 days'
                );
            """))
            log.info("  TimescaleDB hypertable enabled on dwlr_readings ✅")
        except Exception as e:
            log.warning(f"  Hypertable skipped (plain PostgreSQL fallback): {e}")

        # Indexes
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_readings_station_time
                ON dwlr_readings (station_id, timestamp DESC);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stations_state
                ON stations (state);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stations_district
                ON stations (district);
            """))
            log.info("  Indexes created ✅")
        except Exception as e:
            log.warning(f"  Index creation skipped: {e}")


# ─────────────────────────────────────────────
# HEALTH CHECK — used by GET /health
# Both names exported so main.py and routes can use either.
# ─────────────────────────────────────────────
def check_connection() -> bool:
    """
    Ping the database. Returns True if reachable, False if not.
    Sync — called by GET /api/health in api/main.py.
    """
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        log.warning(f"  DB health check failed: {e}")
        return False


# Alias — your original database.py exported this name
# Phase 2 main.py uses check_connection(), both work.
check_db_connection = check_connection