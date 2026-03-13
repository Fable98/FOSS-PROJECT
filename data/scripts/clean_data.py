"""
SubTerra — DWLR Data Cleaner
data/scripts/clean_data.py

Takes raw DataFrames (from scraper.py) or CSVs (from raw/) and:
  1. Removes duplicate readings
  2. Fixes / removes missing values
  3. Removes bad / suspect quality readings
  4. Validates water level ranges (0.5m – 150m)
  5. Removes future timestamps
  6. Detects sensor spikes (sudden jumps)
  7. Flags statistical anomalies (rolling Z-score)
  8. Normalises timestamps to IST (Asia/Kolkata)
  9. Standardizes column names and formats
  10. Cleans rainfall data for Task 2
  11. Saves clean data to data/processed/

Can be used two ways:
  A) As a module  — called by scraper.py / db_writer pipeline
  B) As a CLI     — run directly on raw CSV files

Usage (CLI):
  python clean_data.py                   # Clean latest raw files
  python clean_data.py --dry-run         # Check without saving
  python clean_data.py --report          # Print detailed cleaning report
  python clean_data.py --input data/raw/ # Specify input folder
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("subterra.cleaner")

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
RAW_DIR       = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# VALIDATION CONSTANTS
# ─────────────────────────────────────────────
WATER_LEVEL_MIN = 0.5      # metres — below this = sensor error
WATER_LEVEL_MAX = 150.0    # metres — above this = unrealistic
MAX_LEVEL_JUMP  = 5.0      # metres per reading — above this = spike
RAINFALL_MAX    = 500.0    # mm/day — Kerala flood level

REQUIRED_STATION_COLS  = ["station_id", "station_name", "state",
                           "district", "latitude", "longitude"]
REQUIRED_READINGS_COLS = ["station_id", "timestamp", "water_level_m"]

# Quality flags to reject (WRIS convention)
BAD_FLAGS = {"E", "M", "S", "X", "bad", "Bad", "BAD"}

AQUIFER_MAP = {
    "alluvial":  "Alluvial",
    "hard rock": "Hard Rock",
    "hardrock":  "Hard Rock",
    "basalt":    "Basalt",
    "limestone": "Limestone",
    "sandstone": "Sandstone",
    "granite":   "Granite",
    "gneiss":    "Gneiss",
}


# ═══════════════════════════════════════════════════════════════
# STATION CLEANER
# ═══════════════════════════════════════════════════════════════
def clean_stations(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean and validate station master records.

    Steps:
      1. Standardise column names
      2. Add missing required columns
      3. Remove duplicate station IDs
      4. Drop rows with no station_id
      5. Validate lat/lon within India bounding box
      6. Normalise string columns (title case)
      7. Validate well depth (5m – 500m)
      8. Standardise aquifer type

    Returns: (cleaned_df, report_dict)
    """
    report         = {}
    original_count = len(df)
    log.info(f"Cleaning stations — {original_count} rows")

    df = df.copy()

    # 1 — Standardise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # 2 — Add missing required columns
    missing_cols = [c for c in REQUIRED_STATION_COLS if c not in df.columns]
    if missing_cols:
        log.warning(f"  Missing columns: {missing_cols} — adding empty")
        for col in missing_cols:
            df[col] = None

    # 3 — Remove duplicate station IDs
    before = len(df)
    df = df.drop_duplicates(subset=["station_id"], keep="first")
    report["duplicate_stations_removed"] = before - len(df)
    if report["duplicate_stations_removed"]:
        log.info(f"  Removed {report['duplicate_stations_removed']} duplicate station IDs.")

    # 4 — Drop rows with no station_id
    before = len(df)
    df = df.dropna(subset=["station_id"])
    df = df[df["station_id"].astype(str).str.strip() != ""]
    report["no_id_removed"] = before - len(df)
    if report["no_id_removed"]:
        log.info(f"  Removed {report['no_id_removed']} rows with empty station_id.")

    # 5 — Validate lat/lon within India bounding box (lat 6–38, lon 68–98)
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    invalid_coords  = (
        (df["latitude"]  < 6)  | (df["latitude"]  > 38) |
        (df["longitude"] < 68) | (df["longitude"] > 98)
    )
    report["invalid_coords"] = int(invalid_coords.sum())
    if report["invalid_coords"]:
        log.warning(f"  {report['invalid_coords']} stations outside India bounding box — dropping.")
        df = df[~invalid_coords]

    # 6 — Normalise string columns
    for col in ["state", "district", "block", "station_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()
            df[col] = df[col].replace("Nan", np.nan)

    # 7 — Validate well depth (5m – 500m)
    if "well_depth_m" in df.columns:
        df["well_depth_m"] = pd.to_numeric(df["well_depth_m"], errors="coerce")
        invalid_depth = (df["well_depth_m"] < 5) | (df["well_depth_m"] > 500)
        df.loc[invalid_depth, "well_depth_m"] = np.nan

    # 8 — Standardise aquifer type
    if "aquifer_type" in df.columns:
        df["aquifer_type"] = (
            df["aquifer_type"]
            .astype(str).str.strip().str.lower()
            .map(AQUIFER_MAP)
            .fillna("Unknown")
        )
    else:
        df["aquifer_type"] = "Unknown"

    df["cleaned_at"]      = datetime.now().isoformat()
    report["original_count"] = original_count
    report["final_count"]    = len(df)
    report["rows_removed"]   = original_count - len(df)

    log.info(f"  Stations cleaned: {original_count} → {len(df)}")
    return df.reset_index(drop=True), report


# ═══════════════════════════════════════════════════════════════
# READINGS CLEANER
# ═══════════════════════════════════════════════════════════════
def clean_readings(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean and validate DWLR water level readings.

    Steps:
      1. Check required columns
      2. Parse + validate timestamps (remove nulls, future values)
      3. Normalise timestamps to IST (Asia/Kolkata)
      4. Parse water_level_m as float
      5. Remove physically impossible values (< 0.5m or > 150m)
      6. Remove bad / suspect quality flags
      7. Remove duplicate (station_id, timestamp) pairs
      8. Detect sensor spikes (jump > 5m per reading)
      9. Detect statistical anomalies (rolling Z-score > 3σ)
      10. Sort by station_id, timestamp

    Returns: (cleaned_df, report_dict)
    """
    report         = {}
    original_count = len(df)
    log.info(f"Cleaning readings — {original_count} rows")

    if df.empty:
        log.warning("  Empty readings DataFrame — nothing to clean.")
        return df, {"original_count": 0, "final_count": 0}

    df = df.copy()

    # 1 — Check required columns
    missing = [c for c in REQUIRED_READINGS_COLS if c not in df.columns]
    if missing:
        log.error(f"  CRITICAL: Missing required columns: {missing}")
        return pd.DataFrame(), {"error": f"Missing columns: {missing}"}

    # 2 — Parse timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    bad_ts = df["timestamp"].isna().sum()
    if bad_ts:
        log.warning(f"  {bad_ts} unparseable timestamps — removing.")
        df = df.dropna(subset=["timestamp"])
    report["bad_timestamps_removed"] = int(bad_ts)

    # Remove future timestamps
    now = pd.Timestamp.now(tz="UTC")
    future_mask  = df["timestamp"] > now
    future_count = future_mask.sum()
    if future_count:
        log.warning(f"  {future_count} future timestamps — removing.")
        df = df[~future_mask]
    report["future_timestamps_removed"] = int(future_count)

    # 3 — Normalise to IST
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")

    # 4 — Parse water level
    df["water_level_m"] = pd.to_numeric(df["water_level_m"], errors="coerce")

    # 5 — Remove physically impossible values
    before      = len(df)
    invalid_wl  = (
        (df["water_level_m"] < WATER_LEVEL_MIN) |
        (df["water_level_m"] > WATER_LEVEL_MAX) |
        df["water_level_m"].isna()
    )
    df = df[~invalid_wl]
    report["impossible_values_removed"] = before - len(df)
    if report["impossible_values_removed"]:
        log.info(f"  Removed {report['impossible_values_removed']} impossible water level values.")

    # 6 — Remove bad quality flags
    quality_col = next(
        (c for c in ["data_quality_flag", "data_quality"] if c in df.columns), None
    )
    if quality_col:
        before = len(df)
        df     = df[~df[quality_col].astype(str).str.strip().isin(BAD_FLAGS)]
        report["bad_quality_removed"] = before - len(df)
        if report["bad_quality_removed"]:
            log.info(f"  Removed {report['bad_quality_removed']} bad quality readings.")
    else:
        df["data_quality_flag"] = "G"

    # 7 — Remove duplicates
    before = len(df)
    df     = df.drop_duplicates(subset=["station_id", "timestamp"], keep="first")
    report["duplicate_readings_removed"] = before - len(df)
    if report["duplicate_readings_removed"]:
        log.info(f"  Removed {report['duplicate_readings_removed']} duplicate readings.")

    # 8 — Detect sensor spikes (jump > MAX_LEVEL_JUMP per reading)
    df = df.sort_values(["station_id", "timestamp"])
    df["_prev_level"] = df.groupby("station_id")["water_level_m"].shift(1)
    df["_level_jump"] = (df["water_level_m"] - df["_prev_level"]).abs()
    spike_mask        = (df["_level_jump"] > MAX_LEVEL_JUMP) & df["_prev_level"].notna()

    before = len(df)
    df     = df[~spike_mask]
    report["spikes_removed"] = before - len(df)
    if report["spikes_removed"]:
        log.info(f"  Removed {report['spikes_removed']} sensor spike readings.")
    df = df.drop(columns=["_prev_level", "_level_jump"])

    # 9 — Statistical anomaly detection (rolling Z-score per station)
    df = detect_anomalies(df)
    report["anomalies_flagged"] = int(df.get("is_anomaly", pd.Series(dtype=bool)).sum())
    if report["anomalies_flagged"]:
        log.info(f"  Flagged {report['anomalies_flagged']} statistical anomalies.")

    # 10 — Sort + finalise
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    df["cleaned_at"] = datetime.now().isoformat()

    report["original_count"] = original_count
    report["final_count"]    = len(df)
    report["rows_removed"]   = original_count - len(df)
    report["retention_pct"]  = (
        round((len(df) / original_count) * 100, 1) if original_count else 0
    )

    log.info(
        f"  Readings cleaned: {original_count} → {len(df)} "
        f"({report['retention_pct']}% retained)"
    )
    return df, report


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag statistical anomalies per station using rolling Z-score.
    Anomaly = Z-score > 3σ over a 7-day window (672 readings at 15-min interval).
    Does NOT remove them — marks is_anomaly=True + anomaly_reason for analysts.
    """
    df = df.copy()
    df["is_anomaly"]     = False
    df["anomaly_reason"] = ""

    for sid, grp in df.groupby("station_id"):
        grp = grp.sort_values("timestamp")
        idx = grp.index

        rolling_mean = grp["water_level_m"].rolling(672, min_periods=10).mean()
        rolling_std  = grp["water_level_m"].rolling(672, min_periods=10).std()
        z_scores     = (grp["water_level_m"] - rolling_mean) / \
                        rolling_std.replace(0, np.nan)

        stat_anomaly = z_scores.abs() > 3.0
        df.loc[idx[stat_anomaly], "is_anomaly"]     = True
        df.loc[idx[stat_anomaly], "anomaly_reason"] = "statistical_anomaly"

    return df


# ═══════════════════════════════════════════════════════════════
# RAINFALL CLEANER
# ═══════════════════════════════════════════════════════════════
def clean_rainfall(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Validate and clean IMD rainfall records.

    Steps:
      1. Drop nulls on required fields
      2. Normalise state / district strings
      3. Clamp rainfall_mm to [0, 500]
      4. Parse date field
      5. Remove duplicates on (state, district, date)

    Returns: (cleaned_df, report_dict)
    """
    report         = {}
    original_count = len(df)

    if df.empty:
        return df, {"original_count": 0, "final_count": 0}

    df = df.copy()
    df = df.dropna(subset=["state", "district", "date", "rainfall_mm"])

    for col in ["state", "district"]:
        df[col] = df[col].astype(str).str.strip().str.title()

    df["rainfall_mm"] = pd.to_numeric(df["rainfall_mm"], errors="coerce")
    df["rainfall_mm"] = df["rainfall_mm"].clip(lower=0.0, upper=RAINFALL_MAX)

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])

    before = len(df)
    df     = df.drop_duplicates(subset=["state", "district", "date"])
    report["duplicates_removed"] = before - len(df)
    df = df.sort_values(["state", "district", "date"]).reset_index(drop=True)

    report["original_count"] = original_count
    report["final_count"]    = len(df)
    log.info(f"Rainfall cleaned: {original_count} → {len(df)}")
    return df, report


# ═══════════════════════════════════════════════════════════════
# PIPELINE WRAPPER — used by scraper.py / db_writer
# ═══════════════════════════════════════════════════════════════
def run_cleaning_pipeline(
    readings_df:  pd.DataFrame,
    stations_df:  pd.DataFrame,
    rainfall_df:  pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Run full cleaning pipeline on all three datasets.
    Called by scraper.py write_to_db() and db_writer.py.

    Returns: (clean_readings, clean_stations, clean_rainfall)
    """
    log.info("=== Starting cleaning pipeline ===")
    clean_r,  _ = clean_readings(readings_df)
    clean_s,  _ = clean_stations(stations_df)
    clean_rf, _ = clean_rainfall(rainfall_df)
    log.info("=== Cleaning pipeline complete ===")
    return clean_r, clean_s, clean_rf


# ═══════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════
def save_processed(
    df: pd.DataFrame,
    filename: str,
    output_dir: Path = PROCESSED_DIR,
    dry_run: bool = False,
) -> Optional[Path]:
    """Save cleaned DataFrame to processed/ folder."""
    if df.empty:
        log.warning(f"  Nothing to save for {filename}")
        return None
    filepath = output_dir / filename
    if dry_run:
        log.info(f"  [DRY RUN] Would save {len(df)} rows → {filepath}")
        return filepath
    df.to_csv(filepath, index=False)
    log.info(f"  Saved {len(df)} rows → {filepath}")
    return filepath


# ═══════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════
def print_report(
    stations_report: dict,
    readings_report: dict,
    rainfall_report: dict = None,
):
    """Print a human-readable cleaning summary."""
    print("\n" + "=" * 55)
    print("  SubTerra — Data Cleaning Report")
    print("=" * 55)

    print("\n📍 STATIONS")
    print(f"  Original rows      : {stations_report.get('original_count', 0)}")
    print(f"  Duplicates removed : {stations_report.get('duplicate_stations_removed', 0)}")
    print(f"  No ID removed      : {stations_report.get('no_id_removed', 0)}")
    print(f"  Invalid coords     : {stations_report.get('invalid_coords', 0)}")
    print(f"  Final rows         : {stations_report.get('final_count', 0)}")

    print("\n📊 READINGS")
    print(f"  Original rows      : {readings_report.get('original_count', 0)}")
    print(f"  Bad timestamps     : {readings_report.get('bad_timestamps_removed', 0)}")
    print(f"  Future timestamps  : {readings_report.get('future_timestamps_removed', 0)}")
    print(f"  Impossible values  : {readings_report.get('impossible_values_removed', 0)}")
    print(f"  Bad quality        : {readings_report.get('bad_quality_removed', 0)}")
    print(f"  Duplicates         : {readings_report.get('duplicate_readings_removed', 0)}")
    print(f"  Sensor spikes      : {readings_report.get('spikes_removed', 0)}")
    print(f"  Anomalies flagged  : {readings_report.get('anomalies_flagged', 0)}")
    print(f"  Final rows         : {readings_report.get('final_count', 0)}")
    print(f"  Retention          : {readings_report.get('retention_pct', 0)}%")

    if rainfall_report:
        print("\n🌧  RAINFALL")
        print(f"  Original rows      : {rainfall_report.get('original_count', 0)}")
        print(f"  Duplicates removed : {rainfall_report.get('duplicates_removed', 0)}")
        print(f"  Final rows         : {rainfall_report.get('final_count', 0)}")

    print("=" * 55 + "\n")


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="SubTerra Data Cleaner — cleans raw DWLR data from raw/ folder"
    )
    parser.add_argument("--input",   type=str, default=str(RAW_DIR),
                        help="Input folder (default: data/raw/)")
    parser.add_argument("--output",  type=str, default=str(PROCESSED_DIR),
                        help="Output folder (default: data/processed/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check data without saving")
    parser.add_argument("--report",  action="store_true",
                        help="Print detailed cleaning report")
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("=" * 55)
    log.info("  SubTerra Data Cleaner Starting")
    log.info(f"  Input   : {input_dir}")
    log.info(f"  Output  : {output_dir}")
    log.info(f"  Dry run : {args.dry_run}")
    log.info("=" * 55)

    # Load raw files
    stations_file = input_dir / "stations_latest.csv"
    readings_file = input_dir / "readings_latest.csv"
    rainfall_file = input_dir / "rainfall_latest.csv"

    if not stations_file.exists() or not readings_file.exists():
        log.error("stations_latest.csv or readings_latest.csv not found in input folder.")
        log.error("Run scraper.py first to generate raw data.")
        return

    stations_raw = pd.read_csv(stations_file)
    readings_raw = pd.read_csv(readings_file, parse_dates=["timestamp"])
    rainfall_raw = (
        pd.read_csv(rainfall_file, parse_dates=["date"])
        if rainfall_file.exists()
        else pd.DataFrame(columns=["state", "district", "date", "rainfall_mm"])
    )

    log.info(
        f"Loaded {len(stations_raw)} stations, "
        f"{len(readings_raw)} readings, "
        f"{len(rainfall_raw)} rainfall records."
    )

    # Clean
    stations_clean, stations_report = clean_stations(stations_raw)
    readings_clean, readings_report = clean_readings(readings_raw)
    rainfall_clean, rainfall_report = clean_rainfall(rainfall_raw)

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_processed(stations_clean, f"stations_{ts}.csv",  output_dir, args.dry_run)
    save_processed(readings_clean, f"readings_{ts}.csv",  output_dir, args.dry_run)
    save_processed(rainfall_clean, f"rainfall_{ts}.csv",  output_dir, args.dry_run)
    save_processed(stations_clean, "stations_latest.csv", output_dir, args.dry_run)
    save_processed(readings_clean, "readings_latest.csv", output_dir, args.dry_run)
    save_processed(rainfall_clean, "rainfall_latest.csv", output_dir, args.dry_run)

    if args.report or args.dry_run:
        print_report(stations_report, readings_report, rainfall_report)

    log.info("Cleaning complete ✅")


if __name__ == "__main__":
    main()