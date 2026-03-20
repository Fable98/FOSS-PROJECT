"""
db_writer.py — SubTerra TimescaleDB Writer
Handles all database write operations for the data pipeline.
Uses psycopg2 for direct TimescaleDB interaction.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PGConnection

log = logging.getLogger("db_writer")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://subterra_user:subterra_pass@localhost:5432/subterra",
)


class DBWriter:
    """Wraps a psycopg2 connection with SubTerra-specific write methods."""

    def __init__(self):
        self.conn: PGConnection = psycopg2.connect(DB_URL)
        self.conn.autocommit = False
        log.info("DB connection established.")

    def close(self):
        self.conn.close()
        log.info("DB connection closed.")

    # ── Schema helpers ────────────────────────────────────────────────────────

    def ensure_schema(self):
        """
        Create tables + TimescaleDB hypertable if they don't exist.
        Safe to call on every startup.
        """
        ddl = """
        -- Station master (static)
        CREATE TABLE IF NOT EXISTS stations (
            station_id      TEXT PRIMARY KEY,
            station_name    TEXT,
            latitude        DOUBLE PRECISION NOT NULL,
            longitude       DOUBLE PRECISION NOT NULL,
            state           TEXT,
            district        TEXT,
            block           TEXT,
            well_depth_m    DOUBLE PRECISION,
            aquifer_type    TEXT,
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );

        -- DWLR readings (time-series — will become hypertable)
        CREATE TABLE IF NOT EXISTS dwlr_readings (
            station_id          TEXT        NOT NULL,
            timestamp           TIMESTAMPTZ NOT NULL,
            water_level_m       DOUBLE PRECISION,
            data_quality_flag   TEXT        DEFAULT 'G',
            is_anomaly          BOOLEAN     DEFAULT FALSE,
            anomaly_reason      TEXT        DEFAULT '',
            PRIMARY KEY (station_id, timestamp)
        );

        -- Rainfall (daily, district-level)
        CREATE TABLE IF NOT EXISTS rainfall (
            state           TEXT        NOT NULL,
            district        TEXT        NOT NULL,
            date            DATE        NOT NULL,
            rainfall_mm     DOUBLE PRECISION,
            PRIMARY KEY (state, district, date)
        );
        """

        hypertable_sql = """
        SELECT create_hypertable(
            'dwlr_readings', 'timestamp',
            if_not_exists => TRUE,
            migrate_data   => TRUE
        );
        """

        with self.conn.cursor() as cur:
            cur.execute(ddl)
            try:
                cur.execute(hypertable_sql)
                log.info("TimescaleDB hypertable ensured for dwlr_readings.")
            except psycopg2.errors.UndefinedFunction:
                log.warning(
                    "TimescaleDB extension not found — "
                    "running as plain PostgreSQL (hypertable skipped)."
                )
                self.conn.rollback()
        self.conn.commit()
        log.info("Schema ensured.")

    # ── Station writes ────────────────────────────────────────────────────────

    def upsert_stations(self, df: pd.DataFrame):
        """Insert or update station master records."""
        if df.empty:
            log.warning("upsert_stations called with empty DataFrame.")
            return

        records = df.to_dict(orient="records")
        sql = """
        INSERT INTO stations (
            station_id, station_name, latitude, longitude,
            state, district, block, well_depth_m, aquifer_type, updated_at
        ) VALUES (
            %(station_id)s, %(station_name)s, %(latitude)s, %(longitude)s,
            %(state)s, %(district)s, %(block)s, %(well_depth_m)s,
            %(aquifer_type)s, NOW()
        )
        ON CONFLICT (station_id) DO UPDATE SET
            station_name  = EXCLUDED.station_name,
            latitude      = EXCLUDED.latitude,
            longitude     = EXCLUDED.longitude,
            state         = EXCLUDED.state,
            district      = EXCLUDED.district,
            block         = EXCLUDED.block,
            well_depth_m  = EXCLUDED.well_depth_m,
            aquifer_type  = EXCLUDED.aquifer_type,
            updated_at    = NOW();
        """
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=500)
        self.conn.commit()
        log.info(f"Upserted {len(records)} stations.")

    def station_count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stations;")
            return cur.fetchone()[0]

    def get_all_station_ids(self) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT station_id FROM stations;")
            return [row[0] for row in cur.fetchall()]

    def get_distinct_states(self) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT DISTINCT state FROM stations WHERE state IS NOT NULL;")
            return [row[0] for row in cur.fetchall()]

    # ── Readings writes ───────────────────────────────────────────────────────

    def insert_readings(self, df: pd.DataFrame):
        """
        Bulk-insert DWLR readings.
        Skips rows where (station_id, timestamp) already exist.
        """
        if df.empty:
            log.warning("insert_readings called with empty DataFrame.")
            return

        cols = ["station_id", "timestamp", "water_level_m",
                "data_quality_flag", "is_anomaly", "anomaly_reason"]

        # Add missing optional columns
        for col in cols:
            if col not in df.columns:
                df[col] = None

        records = df[cols].to_dict(orient="records")
        sql = """
        INSERT INTO dwlr_readings (
            station_id, timestamp, water_level_m,
            data_quality_flag, is_anomaly, anomaly_reason
        ) VALUES (
            %(station_id)s, %(timestamp)s, %(water_level_m)s,
            %(data_quality_flag)s, %(is_anomaly)s, %(anomaly_reason)s
        )
        ON CONFLICT (station_id, timestamp) DO NOTHING;
        """
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=1000)
        self.conn.commit()
        log.info(f"Inserted {len(records)} readings.")

    def get_latest_reading_time(self) -> Optional[datetime]:
        """Return the timestamp of the most recent reading in the DB."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT MAX(timestamp) FROM dwlr_readings;")
            result = cur.fetchone()[0]
        if result:
            log.info(f"Latest reading in DB: {result}")
        else:
            log.info("No readings in DB yet.")
        return result

    # ── Rainfall writes ───────────────────────────────────────────────────────

    def upsert_rainfall(self, df: pd.DataFrame):
        """Insert or update daily rainfall records."""
        if df.empty:
            log.warning("upsert_rainfall called with empty DataFrame.")
            return

        records = df[["state", "district", "date", "rainfall_mm"]].to_dict(orient="records")
        sql = """
        INSERT INTO rainfall (state, district, date, rainfall_mm)
        VALUES (%(state)s, %(district)s, %(date)s, %(rainfall_mm)s)
        ON CONFLICT (state, district, date) DO UPDATE SET
            rainfall_mm = EXCLUDED.rainfall_mm;
        """
        with self.conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=500)
        self.conn.commit()
        log.info(f"Upserted {len(records)} rainfall records.")