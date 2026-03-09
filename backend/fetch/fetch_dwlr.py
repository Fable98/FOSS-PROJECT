"""
fetch/fetch_dwlr.py — SubTerra
On-demand DWLR station master + readings fetcher.
Called by FastAPI routes when fresh data is needed.
The continuous scraper (data/scripts/scraper.py) handles background ingestion.
"""

import os
import time
import logging
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("fetch_dwlr")

# ── Config ─────────────────────────────────────────────────────────────────────
WRIS_BASE       = os.getenv("WRIS_BASE_URL", "https://indiawris.gov.in/wris")
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", 3))
RETRY_BACKOFF   = int(os.getenv("RETRY_BACKOFF_SEC", 10))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SEC", 30))
BATCH_SIZE      = 50  # max stations per WRIS API call

HEADERS = {
    "User-Agent": "SubTerra/1.0 CGWB-FOSS-25068",
    "Accept":     "application/json",
}

# Physical bounds for water level (metres below ground surface)
WATER_LEVEL_MIN =   0.0
WATER_LEVEL_MAX = 200.0

# Quality flags to discard
BAD_FLAGS = {"E", "M", "S", "X"}   # Error, Missing, Suspect, Invalid

# Sample data paths (fallback in dev / when API is down)
_HERE           = os.path.dirname(__file__)
SAMPLE_STATIONS = os.path.join(_HERE, "../../data/sample/station_master_sample.csv")
SAMPLE_READINGS = os.path.join(_HERE, "../../data/sample/dwlr_readings_sample.csv")


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None) -> Optional[dict]:
    """GET with retry and exponential backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(
                url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            log.warning(f"HTTP {e.response.status_code} — {url} (attempt {attempt})")
        except requests.exceptions.ConnectionError:
            log.warning(f"Connection error — {url} (attempt {attempt})")
        except requests.exceptions.Timeout:
            log.warning(f"Timeout — {url} (attempt {attempt})")
        except Exception as e:
            log.error(f"Unexpected error — {url}: {e}")
            return None

        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF * (2 ** (attempt - 1))
            log.info(f"Retrying in {wait}s …")
            time.sleep(wait)

    log.error(f"All {MAX_RETRIES} attempts failed — {url}")
    return None


# ── Station Master ─────────────────────────────────────────────────────────────

def fetch_station_master() -> pd.DataFrame:
    """
    Fetch static station metadata from CGWB via India-WRIS.

    Returns DataFrame with columns:
        station_id, station_name, latitude, longitude,
        state, district, block, well_depth_m, aquifer_type

    Falls back to sample CSV if API is unavailable.
    """
    log.info("Fetching Station Master from India-WRIS …")

    data = _get(f"{WRIS_BASE}/api/v1/stations")

    if data and "stations" in data:
        df = pd.DataFrame(data["stations"]).rename(columns={
            "stationId":   "station_id",
            "stationName": "station_name",
            "lat":         "latitude",
            "lon":         "longitude",
            "stateName":   "state",
            "distName":    "district",
            "blockName":   "block",
            "wellDepth":   "well_depth_m",
            "aquiferType": "aquifer_type",
        })
        df = _clean_stations(df)
        log.info(f"Station Master: {len(df)} stations loaded from API.")
        return df

    # Fallback — data.gov.in
    log.warning("WRIS API unavailable — trying data.gov.in fallback …")
    try:
        df = pd.read_csv("https://data.gov.in/resource/dwlr-station-master")
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        df = _clean_stations(df)
        log.info(f"Station Master: {len(df)} stations from data.gov.in.")
        return df
    except Exception as e:
        log.warning(f"data.gov.in fallback failed: {e}")

    # Fallback — bundled sample CSV
    log.warning("Loading bundled sample station master (offline/dev mode).")
    return _clean_stations(pd.read_csv(SAMPLE_STATIONS))


def get_station(station_id: str) -> Optional[dict]:
    """
    Fetch metadata for a single station by ID.
    Returns a dict or None if not found.
    Called by: GET /api/stations/{id}
    """
    log.info(f"Fetching single station: {station_id}")
    data = _get(f"{WRIS_BASE}/api/v1/stations/{station_id}")
    if data and "station" in data:
        return data["station"]

    # Fallback — search sample CSV
    df = pd.read_csv(SAMPLE_STATIONS)
    row = df[df["station_id"] == station_id]
    return row.to_dict(orient="records")[0] if not row.empty else None


def _clean_stations(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalise station master records."""
    df = df.copy()
    df = df.dropna(subset=["station_id", "latitude", "longitude"])

    # India bounding box: lat 6–38°N, lon 68–98°E
    valid = (
        df["latitude"].between(6.0, 38.0) &
        df["longitude"].between(68.0, 98.0)
    )
    n_dropped = (~valid).sum()
    if n_dropped:
        log.warning(f"Dropping {n_dropped} stations outside India bounding box.")
    df = df[valid]

    # Normalise strings
    for col in ["station_name", "state", "district", "block", "aquifer_type"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()

    if "aquifer_type" in df.columns:
        df["aquifer_type"] = df["aquifer_type"].replace(
            {"Nan": "Unknown", "None": "Unknown", "": "Unknown"}
        )
    else:
        df["aquifer_type"] = "Unknown"

    df = df.drop_duplicates(subset=["station_id"]).reset_index(drop=True)
    log.info(f"Stations after cleaning: {len(df)}")
    return df


# ── DWLR Readings ──────────────────────────────────────────────────────────────

def fetch_latest_readings(
    station_ids: list[str],
    since: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Fetch 15-minute DWLR readings for the given station IDs.

    Args:
        station_ids : List of station ID strings.
        since       : Fetch readings after this UTC datetime.
                      Defaults to last 30 minutes.

    Returns DataFrame with columns:
        station_id, timestamp, water_level_m,
        data_quality_flag, is_anomaly, anomaly_reason
    """
    if since is None:
        since = datetime.utcnow() - timedelta(minutes=30)

    since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_str   = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    log.info(
        f"Fetching DWLR readings — {len(station_ids)} stations "
        f"since {since_str} …"
    )

    all_rows      = []
    total_batches = (len(station_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(station_ids), BATCH_SIZE):
        batch     = station_ids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        data = _get(
            f"{WRIS_BASE}/api/v1/readings",
            params={
                "station_ids": ",".join(batch),
                "from":        since_str,
                "to":          now_str,
                "interval":    "15min",
            },
        )
        if data and "readings" in data:
            all_rows.extend(data["readings"])
        else:
            log.warning(f"No readings for batch {batch_num}/{total_batches}")

        time.sleep(0.3)  # polite rate limit

    if not all_rows:
        log.warning("No live readings returned — loading sample data.")
        return _clean_readings(pd.read_csv(SAMPLE_READINGS))

    df = pd.DataFrame(all_rows).rename(columns={
        "stationId":   "station_id",
        "recordedAt":  "timestamp",
        "waterLevel":  "water_level_m",
        "qualityFlag": "data_quality_flag",
    })

    df = _clean_readings(df)
    log.info(f"Readings fetched and cleaned: {len(df)} rows.")
    return df


def fetch_readings_for_station(
    station_id: str,
    hours: int = 24,
) -> pd.DataFrame:
    """
    Convenience wrapper — fetch last N hours of readings for one station.
    Called by: GET /api/task1/{station_id}
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    return fetch_latest_readings([station_id], since=since)


def _clean_readings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate, deduplicate, timezone-normalise, and anomaly-flag readings.
    """
    df = df.copy()

    # 1 — Drop nulls
    df = df.dropna(subset=["station_id", "timestamp", "water_level_m"])

    # 2 — Remove bad quality flags
    if "data_quality_flag" in df.columns:
        df["data_quality_flag"] = df["data_quality_flag"].str.upper().str.strip()
        before = len(df)
        df = df[~df["data_quality_flag"].isin(BAD_FLAGS)]
        removed = before - len(df)
        if removed:
            log.warning(f"Removed {removed} rows with bad quality flags.")
    else:
        df["data_quality_flag"] = "G"

    # 3 — Numeric conversion + physical bounds
    df["water_level_m"] = pd.to_numeric(df["water_level_m"], errors="coerce")
    out_of_range = (
        (df["water_level_m"] < WATER_LEVEL_MIN) |
        (df["water_level_m"] > WATER_LEVEL_MAX)
    )
    if out_of_range.sum():
        log.warning(f"Flagging {out_of_range.sum()} out-of-range readings.")
        df.loc[out_of_range, "data_quality_flag"] = "S"
        df.loc[out_of_range, "water_level_m"]     = np.nan

    # 4 — Timezone → IST
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")

    # 5 — Deduplication
    before = len(df)
    df = df.drop_duplicates(subset=["station_id", "timestamp"])
    if (before - len(df)):
        log.info(f"Removed {before - len(df)} duplicate readings.")

    # 6 — Sort
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    # 7 — Anomaly detection
    df = _detect_anomalies(df)

    return df


def _detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag anomalous readings per station using:
      - Rolling Z-score > 3σ over 7-day window  → statistical spike
      - Drop > 5 m in one 15-min interval        → sudden over-extraction

    Adds columns: is_anomaly (bool), anomaly_reason (str)
    """
    df = df.copy()
    df["is_anomaly"]     = False
    df["anomaly_reason"] = ""

    for sid, grp in df.groupby("station_id"):
        grp = grp.sort_values("timestamp")
        idx = grp.index

        # 7-day rolling window = 7 * 24 * 4 = 672 readings
        rolling_mean = grp["water_level_m"].rolling(672, min_periods=10).mean()
        rolling_std  = grp["water_level_m"].rolling(672, min_periods=10).std()
        z_scores     = (grp["water_level_m"] - rolling_mean) / \
                        rolling_std.replace(0, np.nan)

        stat_spike  = z_scores.abs() > 3.0
        sudden_drop = grp["water_level_m"].diff() > 5.0

        df.loc[idx[stat_spike],  "is_anomaly"]     = True
        df.loc[idx[stat_spike],  "anomaly_reason"] = "statistical_spike"
        df.loc[idx[sudden_drop], "is_anomaly"]     = True
        df.loc[idx[sudden_drop], "anomaly_reason"] += "|sudden_drop"

    n = df["is_anomaly"].sum()
    if n:
        log.info(f"Anomaly detection: {n} readings flagged.")

    return df