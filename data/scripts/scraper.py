"""
SubTerra — DWLR Data Scraper
data/scripts/scraper.py

Fetches groundwater level data from:
  Primary  → India-WRIS GeoServer (WFS) + statewise API
  Fallback → data.gov.in open datasets
  Fallback → Local CSV sample data (offline dev mode)

Also fetches:
  Rainfall → IMD AWS API (for Task 2 recharge estimation)

Usage:
  python scraper.py                          # Continuous loop, all states
  python scraper.py --once                   # Run once and exit
  python scraper.py --state Rajasthan        # Fetch one state
  python scraper.py --district Jaipur        # Fetch one district
  python scraper.py --source sample          # Use local sample data (offline)
  python scraper.py --days 30                # Last 30 days of data
  python scraper.py --refresh                # Force full station master refresh
"""

import argparse
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
# LOGGING
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
BASE_DIR      = Path(__file__).resolve().parent.parent   # data/
RAW_DIR       = BASE_DIR / "raw"
SAMPLE_DIR    = BASE_DIR / "sample"
RAW_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
INDIA_WRIS_BASE  = "https://indiawris.gov.in"
WRIS_GW_API      = f"{INDIA_WRIS_BASE}/api/gwl"
WRIS_STATION_API = f"{INDIA_WRIS_BASE}/api/gwstation"
WRIS_GEOSERVER   = f"{INDIA_WRIS_BASE}/geoserver/wfs"

IMD_BASE         = os.getenv("IMD_BASE_URL", "https://imdaws.imd.gov.in")
DATA_GOV_API     = "https://api.data.gov.in/resource"
CGWB_DATASET_ID  = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"

FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL_SEC", "900"))  # 15 minutes

ALL_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
]
SAMPLE_STATIONS_PER_STATE = 3


def _state_code(state: str) -> str:
    """Build a stable short code for synthetic station IDs."""
    parts = [p for p in str(state).split() if p]
    if len(parts) >= 2:
      return (parts[0][0] + parts[1][0]).upper()
    return str(state)[:2].upper()


# ─────────────────────────────────────────────
# HTTP SESSION — retry + browser headers
# ─────────────────────────────────────────────
def make_session() -> requests.Session:
    """
    Create a requests Session with:
    - Automatic retry on 429 / 5xx (3 attempts, exponential backoff)
    - Browser-like headers to avoid blocks
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,                              # waits: 1s, 2s, 4s
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer":         INDIA_WRIS_BASE,
    })
    return session


# ═══════════════════════════════════════════════════════════════
# FETCHER 1 — Station Master
# ═══════════════════════════════════════════════════════════════
def fetch_station_master(
    session: requests.Session,
    state: str = None,
) -> pd.DataFrame:
    """
    Fetch DWLR station metadata from India-WRIS GeoServer (WFS).
    Falls back to data.gov.in, then local sample CSV.

    Returns DataFrame with columns:
        station_id, station_name, state, district, block,
        latitude, longitude, aquifer_type, well_depth_m, station_type
    """
    log.info(f"Fetching station master — state: {state or 'ALL'}")

    params = {
        "service":      "WFS",
        "version":      "1.0.0",
        "request":      "GetFeature",
        "typeName":     "india-wris:gwl_station",
        "outputFormat": "application/json",
        "maxFeatures":  6000,
    }
    if state:
        params["CQL_FILTER"] = f"state_name='{state}'"

    try:
        resp = session.get(WRIS_GEOSERVER, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        stations = []
        for feature in data.get("features", []):
            props  = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            stations.append({
                "station_id":   props.get("station_id", ""),
                "station_name": props.get("station_name", ""),
                "state":        props.get("state_name", ""),
                "district":     props.get("district_name", ""),
                "block":        props.get("block_name", ""),
                "latitude":     coords[1] if coords else None,
                "longitude":    coords[0] if coords else None,
                "aquifer_type": props.get("aquifer_type", ""),
                "well_depth_m": props.get("well_depth", None),
                "station_type": props.get("station_type", "DWLR"),
            })

        df = pd.DataFrame(stations)                 
        log.info(f"  {len(df)} stations from India-WRIS GeoServer.")
        return df

    except requests.exceptions.ConnectionError:
        log.warning("  GeoServer unreachable — trying data.gov.in fallback …")
        return _station_fallback(state)
    except Exception as e:
        log.warning(f"  GeoServer error: {e} — trying fallback …")
        return _station_fallback(state)


def _station_fallback(state: str = None) -> pd.DataFrame:
    """Fallback 1: data.gov.in → Fallback 2: sample CSV → Fallback 3: synthetic."""
    try:
        params = {
            "api-key": os.getenv(
                "DATA_GOV_API_KEY",
                "579b464db66ec23bdd000001cdd3946e44ce4aad38d76835a8bfe6d"
            ),
            "format":         "json",
            "limit":          500,
            "filters[state]": state or "",
        }
        resp = requests.get(
            f"{DATA_GOV_API}/{CGWB_DATASET_ID}", params=params, timeout=15
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        df = pd.DataFrame(records)
        log.info(f"  {len(df)} stations from data.gov.in fallback.")
        return df
    except Exception as e:
        log.warning(f"  data.gov.in also failed: {e}")

    # Fallback: local sample CSV
    sample_file = SAMPLE_DIR / "station_master_sample.csv"
    if sample_file.exists():
        df = pd.read_csv(sample_file)
        if state:
            df = df[df["state"].str.lower() == state.lower()]
        log.info(f"  {len(df)} stations from sample CSV (offline mode).")
        return df

    # Last resort: synthetic data
    log.warning("  Generating synthetic sample stations.")
    return _generate_sample_stations(state)


# ═══════════════════════════════════════════════════════════════
# FETCHER 2 — DWLR Water Level Readings
# ═══════════════════════════════════════════════════════════════
def fetch_water_levels_batch(
    session: requests.Session,
    state: str,
    district: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """
    Fetch water level time-series for all stations in a state/district.
    Falls back to sample data if API is unreachable.

    Returns DataFrame with columns:
        station_id, station_name, state, district,
        timestamp, water_level_m, data_quality
    """
    log.info(f"Fetching water levels — {state} / {district or 'all districts'}")

    params = {
        "state":    state,
        "district": district or "",
        "from":     (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        "to":       datetime.now().strftime("%Y-%m-%d"),
    }

    try:
        resp = session.get(
            f"{INDIA_WRIS_BASE}/api/gwl/statewise",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for station in data.get("stations", []):
            for reading in station.get("readings", []):
                rows.append({
                    "station_id":    station.get("station_id"),
                    "station_name":  station.get("station_name"),
                    "state":         state,
                    "district":      station.get("district"),
                    "timestamp":     pd.to_datetime(reading.get("timestamp")),
                    "water_level_m": float(reading.get("water_level", 0)),
                    "data_quality_flag": reading.get("quality", "G"),
                })

        df = pd.DataFrame(rows)
        log.info(f"  {len(df)} readings from India-WRIS.")
        return df

    except requests.exceptions.ConnectionError:
        log.warning(f"  India-WRIS unreachable for {state} — using sample data.")
        return _load_sample_readings(state, district, days)
    except Exception as e:
        log.warning(f"  API error for {state}: {e} — using sample data.")
        return _load_sample_readings(state, district, days)


# ═══════════════════════════════════════════════════════════════
# FETCHER 3 — IMD Rainfall
# ═══════════════════════════════════════════════════════════════
def fetch_rainfall(
    session: requests.Session,
    states: list[str],
    target_date: datetime = None,
) -> pd.DataFrame:
    """
    Fetch daily district-level rainfall from IMD AWS.
    Used by Task 2 recharge estimation.

    Returns DataFrame with columns:
        state, district, date, rainfall_mm
    """
    if target_date is None:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y-%m-%d")
    log.info(f"Fetching IMD rainfall — {len(states)} states on {date_str} …")

    try:
        resp = session.get(
            f"{IMD_BASE}/api/rainfall/district",
            params={
                "states": ",".join(states),
                "date":   date_str,
                "format": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for record in data.get("data", []):
            rows.append({
                "state":       record.get("stateName"),
                "district":    record.get("distName"),
                "date":        pd.to_datetime(record.get("date")).date(),
                "rainfall_mm": float(record.get("rainfallMm", 0)),
            })

        df = pd.DataFrame(rows)
        log.info(f"  {len(df)} district rainfall records from IMD.")
        return df

    except Exception as e:
        log.warning(f"  IMD API unavailable: {e} — using sample rainfall data.")
        sample_file = SAMPLE_DIR / "rainfall_sample.csv"
        if sample_file.exists():
            return pd.read_csv(sample_file, parse_dates=["date"])
        return pd.DataFrame(columns=["state", "district", "date", "rainfall_mm"])


# ═══════════════════════════════════════════════════════════════
# SAMPLE / SYNTHETIC DATA
# ═══════════════════════════════════════════════════════════════
def _load_sample_readings(
    state: str,
    district: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """Load readings from sample CSV, or generate synthetic data."""
    sample_file = SAMPLE_DIR / "dwlr_readings_sample.csv"
    if sample_file.exists():
        df = pd.read_csv(sample_file, parse_dates=["timestamp"])
        if state:
            df = df[df.get("state", pd.Series(dtype=str)).str.lower() == state.lower()]
        if district:
            df = df[df.get("district", pd.Series(dtype=str)).str.lower() == district.lower()]
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["timestamp"] >= cutoff]
        log.info(f"  {len(df)} readings from sample CSV.")
        return df

    log.info("  Generating synthetic sample readings.")
    return _generate_sample_readings(state, district, days)


def _generate_sample_stations(state: str = None) -> pd.DataFrame:
    """Generate realistic synthetic station master data."""
    import random
    state_cfg = {
        "Rajasthan":     {"lat": 27.0, "lon": 74.0},
        "Gujarat":       {"lat": 22.5, "lon": 72.0},
        "Maharashtra":   {"lat": 19.0, "lon": 76.0},
        "Uttar Pradesh": {"lat": 26.5, "lon": 80.0},
        "Punjab":        {"lat": 31.0, "lon": 75.0},
        "Haryana":       {"lat": 29.0, "lon": 76.0},
    }
    states_to_gen = [state] if state else ALL_STATES
    rows = []
    for s in states_to_gen:
        cfg = state_cfg.get(s, {"lat": 23.0, "lon": 78.0})
        rng = random.Random(f"stations:{s}")
        code = _state_code(s)
        for i in range(SAMPLE_STATIONS_PER_STATE):
            rows.append({
                "station_id":   f"CGWB_{code}_{i + 1:04d}",
                "station_name": f"{s} Well {i + 1}",
                "state":        s,
                "district":     f"District {i + 1}",
                "block":        f"Block {i + 1}",
                "latitude":     round(cfg["lat"] + rng.uniform(-1, 1), 4),
                "longitude":    round(cfg["lon"] + rng.uniform(-1, 1), 4),
                "aquifer_type": rng.choice(["Alluvial", "Hard Rock", "Basalt"]),
                "well_depth_m": round(rng.uniform(25, 80), 1),
                "station_type": "DWLR",
            })
    return pd.DataFrame(rows)


def _generate_sample_readings(
    state: str,
    district: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """Generate realistic synthetic DWLR readings every 15 minutes."""
    import random
    import math
    base_wl_map = {
        "Rajasthan": 18.0, "Gujarat": 22.0, "Maharashtra": 8.0,
        "Uttar Pradesh": 6.0, "Punjab": 12.0, "Haryana": 11.0,
    }
    base_wl  = base_wl_map.get(state, 10.0)
    stations = _generate_sample_stations(state)
    rows     = []

    for _, stn in stations.iterrows():
        rng = random.Random(f"readings:{stn['station_id']}:{days}")
        station_bias = rng.uniform(-2.8, 2.8)
        long_term_trend = rng.uniform(-0.015, 0.02) / 24
        seasonal_amp = rng.uniform(0.6, 2.2)
        daily_amp = rng.uniform(0.02, 0.12)
        monsoon_gain = rng.uniform(0.8, 2.4)
        recharge_pulse_remaining = 0.0
        ts = datetime.now() - timedelta(days=days)
        start_ts = ts
        while ts <= datetime.now():
            elapsed_days = (ts - start_ts).total_seconds() / 86400
            day_fraction = (ts.hour * 60 + ts.minute) / 1440
            seasonal_wave = seasonal_amp * math.sin((elapsed_days / max(days, 30)) * 2 * math.pi)
            daily_wave = daily_amp * math.sin(day_fraction * 2 * math.pi)

            # Monsoon months get shallower readings (recharge / recovery).
            monsoon_component = 0.0
            if ts.month in [7, 8, 9]:
                monsoon_component = -monsoon_gain
            elif ts.month in [6, 10]:
                monsoon_component = -(monsoon_gain * 0.45)

            # Occasional recharge pulses in wetter months produce short recoveries.
            if ts.hour == 0 and ts.minute == 0 and ts.month in [6, 7, 8, 9, 10] and rng.random() < 0.22:
                recharge_pulse_remaining = rng.uniform(0.15, 0.6)
            pulse_effect = -recharge_pulse_remaining
            recharge_pulse_remaining = max(0.0, recharge_pulse_remaining * 0.94)

            noise = rng.uniform(-0.025, 0.025)
            wl = base_wl + station_bias + (elapsed_days * long_term_trend) + seasonal_wave + daily_wave + monsoon_component + pulse_effect + noise
            wl = round(max(1.0, wl), 2)
            rows.append({
                "station_id":    stn["station_id"],
                "station_name":  stn["station_name"],
                "state":         state,
                "district":      stn["district"],
                "timestamp":     ts,
                "water_level_m": wl,
                "data_quality":  rng.choices(
                    ["Good", "Suspect", "Bad"],
                    weights=[90, 7, 3],
                )[0],
            })
            ts += timedelta(minutes=15)   # 15-min interval matches real DWLR

    return pd.DataFrame(rows)

def _generate_sample_rainfall(stations_df, days: int = 365):
    """
    Generate synthetic daily rainfall for Task 2.
    Monsoon months (Jul-Sep) get heavy rain, other months get minimal.
    """
    import random
    from datetime import datetime, timedelta
 
    if stations_df.empty or "state" not in stations_df.columns:
        return pd.DataFrame(columns=["state", "district", "date", "rainfall_mm"])
 
    rows = []
    end_date   = datetime.now().date()
    start_date = end_date - timedelta(days=max(days, 30))
 
    # Get unique state-district pairs
    if "district" in stations_df.columns:
        pairs = stations_df[["state", "district"]].drop_duplicates().to_dict("records")
    else:
        pairs = [{"state": s, "district": "District 1"} for s in stations_df["state"].unique()]
 
    for pair in pairs:
        rng = random.Random(f"rainfall:{pair['state']}:{pair['district']}:{days}")
        current = start_date
        while current <= end_date:
            month = current.month
            if month in [7, 8, 9]:      # Monsoon
                rainfall = rng.uniform(5, 120)
            elif month in [6, 10]:       # Pre/post monsoon transition
                rainfall = rng.uniform(1, 40)
            elif month in [11, 12, 1]:   # Winter
                rainfall = rng.uniform(0, 8)
            else:                         # Summer / pre-monsoon dry
                rainfall = rng.uniform(0, 3)
 
            # Occasional heavy events
            if rng.random() < 0.08:
                rainfall *= 3
 
            rows.append({
                "state":       pair["state"],
                "district":    pair["district"],
                "date":        current,
                "rainfall_mm": round(min(rainfall, 400), 1),
            })
            current += timedelta(days=1)
 
    log.info(f"Generated {len(rows)} synthetic rainfall records for Task 2.")
    return pd.DataFrame(rows)


def _ensure_rainfall_coverage(
    stations_df: pd.DataFrame,
    rainfall_df: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    """Backfill rainfall for offline/demo runs when station coverage is missing."""
    if stations_df.empty:
        return rainfall_df

    required_pairs = {
        (str(row["state"]).strip().title(), str(row["district"]).strip().title())
        for _, row in stations_df[["state", "district"]].drop_duplicates().iterrows()
    }
    provided_pairs = set()
    if not rainfall_df.empty and {"state", "district"}.issubset(rainfall_df.columns):
        provided_pairs = {
            (str(row["state"]).strip().title(), str(row["district"]).strip().title())
            for _, row in rainfall_df[["state", "district"]].drop_duplicates().iterrows()
        }

    if not rainfall_df.empty and required_pairs.issubset(provided_pairs):
        return rainfall_df

    log.info("Rainfall coverage incomplete for fallback data — generating synthetic rainfall.")
    return _generate_sample_rainfall(stations_df, days=max(days, 365))


# ═══════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════
def save_raw(df: pd.DataFrame, filename: str) -> Path:
    """Save DataFrame to raw/ folder as CSV with timestamp + latest copy."""
    if df.empty:
        log.warning(f"  Nothing to save for {filename}")
        return None
    filepath = RAW_DIR / filename
    df.to_csv(filepath, index=False)
    log.info(f"  Saved {len(df)} rows → {filepath}")
    return filepath


# ═══════════════════════════════════════════════════════════════
# DB WRITE — clean + write to TimescaleDB
# ═══════════════════════════════════════════════════════════════
def write_to_db(
    stations_df: pd.DataFrame,
    readings_df: pd.DataFrame,
    rainfall_df: pd.DataFrame,
):
    """
    Run cleaning pipeline and write all three datasets to TimescaleDB.
    Skips gracefully if DB is unreachable (e.g. running without Docker).
    """
    try:
        from clean_data import run_cleaning_pipeline
        from db_writer import DBWriter

        clean_r, clean_s, clean_rf = run_cleaning_pipeline(
            readings_df, stations_df, rainfall_df
        )

        db = DBWriter()
        db.ensure_schema()
        db.upsert_stations(clean_s)
        db.insert_readings(clean_r)
        if clean_rf.empty:
            from clean_data import clean_rainfall
            clean_rf, _ = clean_rainfall(_generate_sample_rainfall(clean_s))
        if not clean_rf.empty:
            db.upsert_rainfall(clean_rf)
        db.close()
        log.info("  Written to TimescaleDB ✓")

    except ImportError:
        log.warning("  db_writer not available — skipping DB write.")
    except Exception as e:
        log.error(f"  DB write failed: {e} — data saved to raw/ only.")


# ═══════════════════════════════════════════════════════════════
# SINGLE PIPELINE RUN
# ═══════════════════════════════════════════════════════════════
def run_once(
    state: str = None,
    district: str = None,
    days: int = 30,
    source: str = "live",
    refresh: bool = False,
):
    """Execute one full fetch → save → DB write cycle."""
    log.info("=" * 55)
    log.info("  SubTerra DWLR Scraper — Pipeline Run")
    log.info(f"  State   : {state or 'ALL'}")
    log.info(f"  District: {district or 'ALL'}")
    log.info(f"  Days    : {days}")
    log.info(f"  Source  : {source}")
    log.info("=" * 55)

    start = time.time()

    if source == "sample":
        log.info("Running in SAMPLE mode (offline)")
        stations_df = _generate_sample_stations(state)
        if state:
            readings_df = _generate_sample_readings(state, district, days)
        else:
            readings_df = pd.concat(
                [_generate_sample_readings(s, district, days) for s in ALL_STATES],
                ignore_index=True,
            )
        rainfall_df = _generate_sample_rainfall(stations_df, days=max(days, 365))
    else:
        session = make_session()

        # Step 1 — Station Master
        log.info("Step 1/3 — Fetching station master …")
        stations_df = fetch_station_master(session, state)

        # Step 2 — Water Level Readings
        log.info("Step 2/3 — Fetching water level readings …")
        states_to_fetch = [state] if state else ALL_STATES
        all_readings = []
        for s in states_to_fetch:
            df = fetch_water_levels_batch(session, s, district, days)
            all_readings.append(df)
            time.sleep(0.5)   # polite rate limit

        readings_df = (
            pd.concat(all_readings, ignore_index=True)
            if all_readings else pd.DataFrame()
        )

        # Step 3 — Rainfall
        log.info("Step 3/3 — Fetching IMD rainfall …")
        states_list = [state] if state else ALL_STATES
        rainfall_df = fetch_rainfall(session, states_list)
        rainfall_df = _ensure_rainfall_coverage(stations_df, rainfall_df, days)

    # Save raw files
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_raw(stations_df, f"stations_{ts}.csv")
    save_raw(readings_df, f"readings_{ts}.csv")
    save_raw(rainfall_df, f"rainfall_{ts}.csv")
    save_raw(stations_df, "stations_latest.csv")
    save_raw(readings_df, "readings_latest.csv")
    save_raw(rainfall_df, "rainfall_latest.csv")

    # Write to TimescaleDB
    write_to_db(stations_df, readings_df, rainfall_df)

    elapsed = round(time.time() - start, 2)
    log.info("=" * 55)
    log.info(f"  Done in {elapsed}s")
    log.info(f"  Stations : {len(stations_df)}")
    log.info(f"  Readings : {len(readings_df)}")
    log.info(f"  Rainfall : {len(rainfall_df)}")
    log.info("=" * 55)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="SubTerra DWLR Scraper — fetches groundwater data from India-WRIS"
    )
    parser.add_argument("--state",    type=str,  default=None,   help="State name (default: all)")
    parser.add_argument("--district", type=str,  default=None,   help="District name (default: all)")
    parser.add_argument("--days",     type=int,  default=30,     help="Days of history (default: 30)")
    parser.add_argument("--source",   type=str,  default="live",
                        choices=["live", "sample"],              help="live = India-WRIS, sample = local")
    parser.add_argument("--once",     action="store_true",       help="Run once and exit")
    parser.add_argument("--refresh",  action="store_true",       help="Force full station master refresh")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)

    if args.once:
        run_once(args.state, args.district, args.days, args.source, args.refresh)
    else:
        log.info(f"Starting continuous scraper (interval: {FETCH_INTERVAL}s) …")
        first_run = True
        while True:
            try:
                run_once(
                    args.state, args.district, args.days,
                    args.source, refresh=first_run,
                )
                first_run = False
            except Exception as e:
                log.error(f"Pipeline error: {e}", exc_info=True)
            log.info(f"Sleeping {FETCH_INTERVAL}s …")
            time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()
