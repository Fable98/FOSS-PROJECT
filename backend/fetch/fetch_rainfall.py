"""
fetch/fetch_rainfall.py — SubTerra
On-demand IMD rainfall fetcher.
Called by FastAPI routes for recharge correlation (Task 2).
The continuous scraper (data/scripts/scraper.py) handles background ingestion.
"""

import os
import time
import logging
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Union

log = logging.getLogger("fetch_rainfall")

# ── Config ─────────────────────────────────────────────────────────────────────
IMD_BASE        = os.getenv("IMD_BASE_URL", "https://imdaws.imd.gov.in")
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", 3))
RETRY_BACKOFF   = int(os.getenv("RETRY_BACKOFF_SEC", 10))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SEC", 30))

HEADERS = {
    "User-Agent": "SubTerra/1.0 CGWB-FOSS-25068",
    "Accept":     "application/json",
}

# Physical bounds: 500 mm/day is extreme but real (Kerala floods)
RAINFALL_MAX = 500.0

# Sample data path
_HERE          = os.path.dirname(__file__)
SAMPLE_RAINFALL = os.path.join(_HERE, "../../data/sample/rainfall_sample.csv")


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


# ── Rainfall Fetch ─────────────────────────────────────────────────────────────

def fetch_rainfall_by_date(
    states: list[str],
    target_date: Optional[Union[date, datetime]] = None,
) -> pd.DataFrame:
    """
    Fetch daily district-level rainfall from IMD for a given date.

    Args:
        states      : List of state name strings.
        target_date : Date to fetch rainfall for. Defaults to today.

    Returns DataFrame with columns:
        state, district, date, rainfall_mm

    Falls back to sample CSV if API is unavailable.
    """
    if target_date is None:
        target_date = datetime.utcnow().date()
    if isinstance(target_date, datetime):
        target_date = target_date.date()

    date_str = target_date.strftime("%Y-%m-%d")
    log.info(f"Fetching IMD rainfall — {len(states)} states on {date_str} …")

    data = _get(
        f"{IMD_BASE}/api/rainfall/district",
        params={
            "states": ",".join(states),
            "date":   date_str,
            "format": "json",
        },
    )

    if data and "data" in data:
        df = pd.DataFrame(data["data"]).rename(columns={
            "stateName":  "state",
            "distName":   "district",
            "date":       "date",
            "rainfallMm": "rainfall_mm",
        })
        df = _clean_rainfall(df)
        log.info(f"Rainfall: {len(df)} district records from IMD API.")
        return df

    log.warning("IMD API unavailable — loading sample rainfall data.")
    return _clean_rainfall(pd.read_csv(SAMPLE_RAINFALL))


def fetch_rainfall_range(
    states: list[str],
    start_date: Union[date, datetime],
    end_date: Union[date, datetime],
) -> pd.DataFrame:
    """
    Fetch rainfall for a date range by calling fetch_rainfall_by_date per day.
    Used by Task 2 recharge correlation (needs multi-day rainfall history).

    Args:
        states     : List of state name strings.
        start_date : Start of range (inclusive).
        end_date   : End of range (inclusive).

    Returns combined DataFrame sorted by state, district, date.
    """
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()

    log.info(
        f"Fetching rainfall range {start_date} → {end_date} "
        f"for {len(states)} states …"
    )

    frames = []
    current = start_date
    while current <= end_date:
        df = fetch_rainfall_by_date(states, target_date=current)
        frames.append(df)
        current += timedelta(days=1)
        time.sleep(0.2)  # polite rate limit

    if not frames:
        log.warning("No rainfall data fetched for range.")
        return pd.DataFrame(columns=["state", "district", "date", "rainfall_mm"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["state", "district", "date"])
    combined = combined.sort_values(["state", "district", "date"]).reset_index(drop=True)

    log.info(f"Rainfall range fetched: {len(combined)} total records.")
    return combined


def fetch_rainfall_for_district(
    state: str,
    district: str,
    days: int = 30,
) -> pd.DataFrame:
    """
    Convenience wrapper — fetch last N days of rainfall for one district.
    Called by: GET /api/task2/{station_id} (recharge estimation)
    """
    end   = datetime.utcnow().date()
    start = end - timedelta(days=days)
    df    = fetch_rainfall_range([state], start_date=start, end_date=end)

    # Filter to requested district
    result = df[
        (df["state"].str.lower()    == state.lower()) &
        (df["district"].str.lower() == district.lower())
    ].reset_index(drop=True)

    log.info(
        f"Rainfall for {district}, {state} "
        f"(last {days} days): {len(result)} records."
    )
    return result


def fetch_premonsoon_postmonsoon(
    states: list[str],
    year: int,
) -> dict[str, pd.DataFrame]:
    """
    Fetch pre-monsoon (May–June) and post-monsoon (Oct–Nov) rainfall
    for a given year. Used by Task 2 net recharge calculation.

    Returns:
        {
            "pre_monsoon":  DataFrame,   # May–June
            "post_monsoon": DataFrame,   # Oct–Nov
        }
    """
    log.info(f"Fetching pre/post monsoon rainfall for {year} …")

    pre_start  = date(year, 5, 1)
    pre_end    = date(year, 6, 30)
    post_start = date(year, 10, 1)
    post_end   = date(year, 11, 30)

    pre_monsoon  = fetch_rainfall_range(states, pre_start,  pre_end)
    post_monsoon = fetch_rainfall_range(states, post_start, post_end)

    return {
        "pre_monsoon":  pre_monsoon,
        "post_monsoon": post_monsoon,
    }


# ── Cleaning ───────────────────────────────────────────────────────────────────

def _clean_rainfall(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and clean IMD rainfall records.

    - Drop nulls on required fields
    - Clamp rainfall_mm to [0, 500]
    - Remove duplicate (state, district, date) entries
    - Normalise string columns
    """
    df = df.copy()

    # Drop nulls
    df = df.dropna(subset=["state", "district", "date", "rainfall_mm"])

    # Normalise strings
    for col in ["state", "district"]:
        df[col] = df[col].astype(str).str.strip().str.title()

    # Numeric conversion + clamp
    df["rainfall_mm"] = pd.to_numeric(df["rainfall_mm"], errors="coerce")
    df["rainfall_mm"] = df["rainfall_mm"].clip(lower=0.0, upper=RAINFALL_MAX)

    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])

    # Deduplication — keep first occurrence
    df = df.drop_duplicates(subset=["state", "district", "date"])
    df = df.sort_values(["state", "district", "date"]).reset_index(drop=True)

    log.info(f"Rainfall cleaned: {len(df)} records.")
    return df