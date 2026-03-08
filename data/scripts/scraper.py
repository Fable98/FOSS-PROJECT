"""
SubTerra — DWLR Data Scraper
data/scripts/scraper.py

Fetches groundwater level data from:
  Primary  → India-WRIS (indiawris.gov.in)
  Fallback → data.gov.in open datasets
  Fallback → Local CSV sample data

Usage:
  python scraper.py                         # Fetch all states
  python scraper.py --state Rajasthan       # Fetch one state
  python scraper.py --state Rajasthan --district Jaipur
  python scraper.py --source sample         # Use local sample data (offline)
  python scraper.py --days 30               # Last 30 days of data
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("subterra.scraper")

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent   # data/
RAW_DIR     = BASE_DIR / "raw"
SAMPLE_DIR  = BASE_DIR / "sample"
RAW_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
INDIA_WRIS_BASE  = "https://indiawris.gov.in"
WRIS_GW_API      = f"{INDIA_WRIS_BASE}/api/gwl"           # Groundwater level API
WRIS_STATION_API = f"{INDIA_WRIS_BASE}/api/gwstation"     # Station master API
WRIS_GEOSERVER   = f"{INDIA_WRIS_BASE}/geoserver/wfs"     # GeoServer WFS endpoint

DATA_GOV_API     = "https://api.data.gov.in/resource"
CGWB_DATASET_ID  = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"  # CGWB GW dataset

# All Indian states SubTerra monitors
ALL_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
]

# ─────────────────────────────────────────────
# HTTP SESSION — with retry logic
# ─────────────────────────────────────────────
def make_session() -> requests.Session:
    """
    Create a requests session with:
    - Automatic retry on failure (3 times)
    - 10 second timeout
    - Browser-like headers to avoid blocks
    """
    session = requests.Session()

    retry = Retry(
        total=3,                        # retry 3 times total
        backoff_factor=1,               # wait 1s, 2s, 4s between retries
        status_forcelist=[429, 500, 502, 503, 504],  # retry on these status codes
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer": INDIA_WRIS_BASE,
    })

    return session


# ═══════════════════════════════════════════════════════════════
# FETCHER 1 — India-WRIS Station Master
# Gets list of all DWLR stations with lat/lon/district info
# ═══════════════════════════════════════════════════════════════
def fetch_station_master(session: requests.Session, state: str = None) -> pd.DataFrame:
    """
    Fetch DWLR station metadata from India-WRIS GeoServer.
    Returns DataFrame with station ID, name, location, aquifer info.
    """
    log.info(f"Fetching station master — state: {state or 'ALL'}")

    # WFS request to get all groundwater stations
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "india-wris:gwl_station",
        "outputFormat": "application/json",
        "maxFeatures": 6000,
    }

    if state:
        params["CQL_FILTER"] = f"state_name='{state}'"

    try:
        response = session.get(WRIS_GEOSERVER, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        stations = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            stations.append({
                "station_id":    props.get("station_id", ""),
                "station_name":  props.get("station_name", ""),
                "state":         props.get("state_name", ""),
                "district":      props.get("district_name", ""),
                "block":         props.get("block_name", ""),
                "latitude":      coords[1] if coords else None,
                "longitude":     coords[0] if coords else None,
                "aquifer_type":  props.get("aquifer_type", ""),
                "well_depth_m":  props.get("well_depth", None),
                "station_type":  props.get("station_type", "DWLR"),
            })

        df = pd.DataFrame(stations)
        log.info(f"  Fetched {len(df)} stations from India-WRIS GeoServer")
        return df

    except requests.exceptions.ConnectionError:
        log.warning("  India-WRIS GeoServer unreachable — trying fallback")
        return fetch_station_master_fallback(state)
    except Exception as e:
        log.warning(f"  GeoServer error: {e} — trying fallback")
        return fetch_station_master_fallback(state)


def fetch_station_master_fallback(state: str = None) -> pd.DataFrame:
    """
    Fallback: fetch station data from data.gov.in open API
    """
    log.info("  Trying data.gov.in fallback for station master...")
    try:
        params = {
            "api-key": os.getenv("DATA_GOV_API_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad38d76835a8bfe6d"),
            "format": "json",
            "limit": 500,
            "filters[state]": state or "",
        }
        response = requests.get(
            f"{DATA_GOV_API}/{CGWB_DATASET_ID}",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        records = response.json().get("records", [])
        df = pd.DataFrame(records)
        log.info(f"  Fetched {len(df)} stations from data.gov.in")
        return df

    except Exception as e:
        log.warning(f"  data.gov.in also failed: {e} — using sample data")
        return load_sample_stations(state)


# ═══════════════════════════════════════════════════════════════
# FETCHER 2 — India-WRIS Water Level Readings
# Gets actual DWLR water level time-series data
# ═══════════════════════════════════════════════════════════════
def fetch_water_levels(
    session: requests.Session,
    station_id: str,
    days: int = 30,
) -> pd.DataFrame:
    """
    Fetch water level time-series for a single DWLR station.
    Returns DataFrame with timestamp and water_level_m columns.
    """
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=days)

    params = {
        "station_id": station_id,
        "from_date":  start_date.strftime("%Y-%m-%d"),
        "to_date":    end_date.strftime("%Y-%m-%d"),
        "type":       "DWLR",
    }

    try:
        response = session.get(WRIS_GW_API, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        readings = []
        for record in data.get("data", []):
            readings.append({
                "station_id":    station_id,
                "timestamp":     pd.to_datetime(record.get("date_time")),
                "water_level_m": float(record.get("water_level", 0)),
                "data_quality":  record.get("quality_flag", "Good"),
            })

        return pd.DataFrame(readings)

    except Exception as e:
        log.debug(f"  Could not fetch readings for {station_id}: {e}")
        return pd.DataFrame()


def fetch_water_levels_batch(
    session: requests.Session,
    state: str,
    district: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """
    Fetch water levels for all stations in a state/district.
    Tries India-WRIS state-level report endpoint first.
    """
    log.info(f"Fetching water levels — {state} / {district or 'all districts'}")

    # Try the state-level report endpoint (returns all stations at once)
    params = {
        "state":    state,
        "district": district or "",
        "from":     (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        "to":       datetime.now().strftime("%Y-%m-%d"),
    }

    try:
        response = session.get(
            f"{INDIA_WRIS_BASE}/api/gwl/statewise",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        all_readings = []
        for station in data.get("stations", []):
            for reading in station.get("readings", []):
                all_readings.append({
                    "station_id":    station.get("station_id"),
                    "station_name":  station.get("station_name"),
                    "state":         state,
                    "district":      station.get("district"),
                    "timestamp":     pd.to_datetime(reading.get("timestamp")),
                    "water_level_m": float(reading.get("water_level", 0)),
                    "data_quality":  reading.get("quality", "Good"),
                })

        df = pd.DataFrame(all_readings)
        log.info(f"  Fetched {len(df)} readings from India-WRIS")
        return df

    except requests.exceptions.ConnectionError:
        log.warning("  India-WRIS unreachable — using sample data")
        return load_sample_readings(state, district, days)
    except Exception as e:
        log.warning(f"  API error: {e} — using sample data")
        return load_sample_readings(state, district, days)


# ═══════════════════════════════════════════════════════════════
# SAMPLE DATA LOADERS — Used when India-WRIS is unreachable
# ═══════════════════════════════════════════════════════════════
def load_sample_stations(state: str = None) -> pd.DataFrame:
    """Load station data from local sample CSV files."""
    sample_file = SAMPLE_DIR / "stations.csv"

    if sample_file.exists():
        df = pd.read_csv(sample_file)
        if state:
            df = df[df["state"].str.lower() == state.lower()]
        log.info(f"  Loaded {len(df)} stations from sample data")
        return df

    # If no sample file — generate minimal sample
    log.info("  Generating minimal sample station data")
    return generate_sample_stations(state)


def load_sample_readings(
    state: str,
    district: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """Load readings from local sample CSV or generate synthetic data."""
    sample_file = SAMPLE_DIR / "readings.csv"

    if sample_file.exists():
        df = pd.read_csv(sample_file, parse_dates=["timestamp"])
        if state:
            df = df[df["state"].str.lower() == state.lower()]
        if district:
            df = df[df["district"].str.lower() == district.lower()]
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["timestamp"] >= cutoff]
        log.info(f"  Loaded {len(df)} readings from sample file")
        return df

    log.info("  Generating synthetic sample readings")
    return generate_sample_readings(state, district, days)


# ═══════════════════════════════════════════════════════════════
# SAMPLE DATA GENERATOR — Realistic synthetic DWLR data
# ═══════════════════════════════════════════════════════════════
def generate_sample_stations(state: str = None) -> pd.DataFrame:
    """Generate realistic sample station master data."""
    import random

    state_config = {
        "Rajasthan":     {"base_lat": 27.0, "base_lon": 74.0, "base_wl": 18.0},
        "Gujarat":       {"base_lat": 22.5, "base_lon": 72.0, "base_wl": 22.0},
        "Maharashtra":   {"base_lat": 19.0, "base_lon": 76.0, "base_wl":  8.0},
        "Uttar Pradesh": {"base_lat": 26.5, "base_lon": 80.0, "base_wl":  6.0},
        "Punjab":        {"base_lat": 31.0, "base_lon": 75.0, "base_wl": 12.0},
        "Haryana":       {"base_lat": 29.0, "base_lon": 76.0, "base_wl": 11.0},
    }

    states_to_gen = [state] if state else list(state_config.keys())
    rows = []
    station_num = 1

    for s in states_to_gen:
        cfg = state_config.get(s, {"base_lat": 23.0, "base_lon": 78.0, "base_wl": 10.0})
        for i in range(5):
            rows.append({
                "station_id":   f"CGWB_{s[:2].upper()}_{station_num:04d}",
                "station_name": f"{s} Well {i + 1}",
                "state":        s,
                "district":     f"District {i + 1}",
                "block":        f"Block {i + 1}",
                "latitude":     round(cfg["base_lat"] + random.uniform(-1, 1), 4),
                "longitude":    round(cfg["base_lon"] + random.uniform(-1, 1), 4),
                "aquifer_type": random.choice(["Alluvial", "Hard Rock", "Basalt"]),
                "well_depth_m": round(random.uniform(25, 80), 1),
                "station_type": "DWLR",
            })
            station_num += 1

    return pd.DataFrame(rows)


def generate_sample_readings(
    state: str,
    district: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """Generate realistic synthetic DWLR readings every 6 hours."""
    import random

    state_base_wl = {
        "Rajasthan": 18.0, "Gujarat": 22.0, "Maharashtra": 8.0,
        "Uttar Pradesh": 6.0, "Punjab": 12.0, "Haryana": 11.0,
    }
    base_wl = state_base_wl.get(state, 10.0)

    stations = generate_sample_stations(state)
    rows = []

    for _, station in stations.iterrows():
        wl = base_wl + random.uniform(-2, 2)
        current_time = datetime.now() - timedelta(days=days)

        while current_time <= datetime.now():
            # Small random fluctuation every 6 hours
            wl += random.uniform(-0.05, 0.04)
            wl = round(max(1.0, wl), 2)    # never go below 1m

            rows.append({
                "station_id":    station["station_id"],
                "station_name":  station["station_name"],
                "state":         state,
                "district":      station["district"],
                "timestamp":     current_time,
                "water_level_m": wl,
                "data_quality":  random.choices(
                    ["Good", "Good", "Good", "Suspect"],
                    weights=[80, 10, 5, 5],
                )[0],
            })
            current_time += timedelta(hours=6)

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════
# SAVE — Write fetched data to raw/ folder
# ═══════════════════════════════════════════════════════════════
def save_raw(df: pd.DataFrame, filename: str) -> Path:
    """Save DataFrame to raw/ folder as CSV."""
    if df.empty:
        log.warning(f"  Nothing to save for {filename}")
        return None

    filepath = RAW_DIR / filename
    df.to_csv(filepath, index=False)
    log.info(f"  Saved {len(df)} rows → {filepath}")
    return filepath


# ═══════════════════════════════════════════════════════════════
# MAIN — Entry point
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="SubTerra DWLR Data Scraper — fetches groundwater data from India-WRIS"
    )
    parser.add_argument("--state",    type=str, default=None,   help="State name (default: all states)")
    parser.add_argument("--district", type=str, default=None,   help="District name (default: all districts)")
    parser.add_argument("--days",     type=int, default=30,     help="Number of days of history (default: 30)")
    parser.add_argument("--source",   type=str, default="live", choices=["live", "sample"],
                        help="Data source: live = India-WRIS, sample = local files")
    args = parser.parse_args()

    log.info("=" * 55)
    log.info("  SubTerra DWLR Scraper Starting")
    log.info(f"  State    : {args.state or 'ALL'}")
    log.info(f"  District : {args.district or 'ALL'}")
    log.info(f"  Days     : {args.days}")
    log.info(f"  Source   : {args.source}")
    log.info("=" * 55)

    start_time = time.time()

    if args.source == "sample":
        # ── Offline mode — use local sample data ──
        log.info("Running in SAMPLE mode (offline)")
        stations = load_sample_stations(args.state)
        readings = load_sample_readings(args.state, args.district, args.days)

    else:
        # ── Live mode — fetch from India-WRIS ──
        session = make_session()

        # Step 1: Fetch station master
        log.info("Step 1/2 — Fetching station master data...")
        stations = fetch_station_master(session, args.state)

        # Step 2: Fetch water level readings
        log.info("Step 2/2 — Fetching water level readings...")
        states_to_fetch = [args.state] if args.state else ALL_STATES[:5]  # limit in dev

        all_readings = []
        for state in states_to_fetch:
            df = fetch_water_levels_batch(session, state, args.district, args.days)
            all_readings.append(df)
            time.sleep(1)   # be polite — don't hammer the server

        readings = pd.concat(all_readings, ignore_index=True) if all_readings else pd.DataFrame()

    # Step 3: Save to raw/
    log.info("Saving data...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_raw(stations, f"stations_{timestamp}.csv")
    save_raw(readings, f"readings_{timestamp}.csv")

    # Also save as latest (overwrite)
    save_raw(stations, "stations_latest.csv")
    save_raw(readings, "readings_latest.csv")

    elapsed = round(time.time() - start_time, 2)

    log.info("=" * 55)
    log.info(f"  Done in {elapsed}s")
    log.info(f"  Stations : {len(stations)}")
    log.info(f"  Readings : {len(readings)}")
    log.info(f"  Saved to : {RAW_DIR}")
    log.info("=" * 55)


if __name__ == "__main__":
    main()