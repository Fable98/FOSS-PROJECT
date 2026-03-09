-- ── SubTerra Database Init ──────────────────────────────────────────────────
-- Runs automatically when the TimescaleDB container starts for the first time.
-- This file maps to: backend/db/init.sql

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ── Station Master ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stations (
    station_id      TEXT            PRIMARY KEY,
    station_name    TEXT,
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    state           TEXT,
    district        TEXT,
    block           TEXT,
    well_depth_m    DOUBLE PRECISION,
    aquifer_type    TEXT,
    updated_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- ── DWLR Readings (TimescaleDB Hypertable) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS dwlr_readings (
    station_id          TEXT            NOT NULL,
    timestamp           TIMESTAMPTZ     NOT NULL,
    water_level_m       DOUBLE PRECISION,
    data_quality_flag   TEXT            DEFAULT 'G',
    is_anomaly          BOOLEAN         DEFAULT FALSE,
    anomaly_reason      TEXT            DEFAULT '',
    PRIMARY KEY (station_id, timestamp)
);

-- Convert to hypertable partitioned by time (7-day chunks)
SELECT create_hypertable(
    'dwlr_readings',
    'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists       => TRUE
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_readings_station
    ON dwlr_readings (station_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_readings_anomaly
    ON dwlr_readings (is_anomaly, timestamp DESC)
    WHERE is_anomaly = TRUE;

-- ── Rainfall ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rainfall (
    state           TEXT    NOT NULL,
    district        TEXT    NOT NULL,
    date            DATE    NOT NULL,
    rainfall_mm     DOUBLE PRECISION,
    PRIMARY KEY (state, district, date)
);

CREATE INDEX IF NOT EXISTS idx_rainfall_district
    ON rainfall (state, district, date DESC);

-- ── Continuous Aggregate: daily average water level per station ───────────────
-- This pre-computes daily summaries so Task 1 queries are fast.
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_water_level
WITH (timescaledb.continuous) AS
    SELECT
        station_id,
        time_bucket('1 day', timestamp) AS day,
        AVG(water_level_m)              AS avg_level_m,
        MIN(water_level_m)              AS min_level_m,
        MAX(water_level_m)              AS max_level_m,
        COUNT(*)                        AS reading_count
    FROM dwlr_readings
    WHERE data_quality_flag NOT IN ('E', 'M', 'S', 'X')
    GROUP BY station_id, day
WITH NO DATA;

-- Refresh policy: update daily aggregate every hour
SELECT add_continuous_aggregate_policy('daily_water_level',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);