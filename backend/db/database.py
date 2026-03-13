"""
SubTerra — Database Connection & Session Management
backend/app/models/database.py

Responsibilities:
  - Create async SQLAlchemy engine from config.DATABASE_URL
  - Provide get_db() dependency for FastAPI routes
  - init_db() — creates tables from station.py models on startup
  - check_db_connection() — used by /health endpoint

Important:
  The pipeline (scraper → clean_data → db_writer) writes to the DB
  directly via psycopg2 (synchronous).

  FastAPI routes READ from the DB via SQLAlchemy async session.

  Both talk to the same tables defined in station.py:
    - stations
    - dwlr_readings
    - rainfall
"""

import logging
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.sql import text

from app.config import settings
from app.models.station import Base   # Station, DWLRReading, Rainfall

log = logging.getLogger("subterra.database")

# ─────────────────────────────────────────────
# ENGINE
# asyncpg is the async PostgreSQL driver.
# Convert postgresql:// → postgresql+asyncpg://
# ─────────────────────────────────────────────
DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,    # logs every SQL query when DEBUG=True
    pool_size=10,           # keep 10 connections open
    max_overflow=20,        # allow 20 extra under heavy load
    pool_pre_ping=True,     # test connection before using it
)

# ─────────────────────────────────────────────
# SESSION FACTORY
# One session per API request — never share sessions.
# ─────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # keep objects usable after commit
)


# ─────────────────────────────────────────────
# DEPENDENCY — injected into every route
# ─────────────────────────────────────────────
async def get_db():
    """
    FastAPI dependency — provides a DB session per request.

    Usage in any route:
        from sqlalchemy.ext.asyncio import AsyncSession
        from fastapi import Depends
        from app.models.database import get_db

        @router.get("/something")
        async def my_route(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Station))
            ...

    Commits on success, rolls back on any exception,
    always closes the session when request is done.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─────────────────────────────────────────────
# INIT — called once at startup from main.py
# ─────────────────────────────────────────────
async def init_db():
    """
    Creates all three tables if they don't already exist:
      - stations       (from Station model)
      - dwlr_readings  (from DWLRReading model)
      - rainfall       (from Rainfall model)

    Also tries to enable TimescaleDB hypertable on dwlr_readings
    for fast time-series queries. Falls back silently if TimescaleDB
    is not available (plain PostgreSQL still works).

    Note: db_writer.py also calls ensure_schema() via psycopg2
    on pipeline startup. Both are safe to call multiple times —
    all DDL uses IF NOT EXISTS.
    """
    async with engine.begin() as conn:

        # Create all tables from station.py
        await conn.run_sync(Base.metadata.create_all)
        log.info("  Tables created (stations, dwlr_readings, rainfall) ✅")

        # Enable TimescaleDB hypertable on dwlr_readings
        # Partitions data by 7-day chunks — makes queries like
        # "last 30 days for station X" extremely fast
        try:
            await conn.execute(text("""
                SELECT create_hypertable(
                    'dwlr_readings',
                    'timestamp',
                    if_not_exists      => TRUE,
                    migrate_data       => TRUE,
                    chunk_time_interval => INTERVAL '7 days'
                );
            """))
            log.info("  TimescaleDB hypertable enabled on dwlr_readings ✅")
        except Exception as e:
            log.warning(f"  Hypertable skipped: {e}")
            log.warning("  Running on plain PostgreSQL — time-series queries will be slower")

        # Composite index on station_id + timestamp DESC
        # Speeds up "get latest N readings for station X" queries
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_readings_station_time
                ON dwlr_readings (station_id, timestamp DESC);
            """))

            # Index for state-level queries (summary dashboard)
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stations_state
                ON stations (state);
            """))

            # Index for district-level queries
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stations_district
                ON stations (district);
            """))

            log.info("  Indexes created ✅")
        except Exception as e:
            log.warning(f"  Index creation skipped: {e}")


# ─────────────────────────────────────────────
# HEALTH CHECK — used by /health endpoint
# ─────────────────────────────────────────────
async def check_db_connection() -> bool:
    """
    Ping the database.
    Returns True if reachable, False if not.
    Used by GET /health in main.py.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        log.warning(f"  DB health check failed: {e}")
        return False
