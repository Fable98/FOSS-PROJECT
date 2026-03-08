"""
SubTerra — DWLR Data Cleaner
data/scripts/clean_data.py

Takes raw CSVs from scraper.py and:
  1. Removes duplicate readings
  2. Fixes missing values
  3. Removes bad/suspect readings
  4. Standardizes column names and formats
  5. Validates water level ranges
  6. Saves clean data to data/processed/

Usage:
  python clean_data.py                          # Clean latest raw files
  python clean_data.py --input data/raw/        # Specify input folder
  python clean_data.py --dry-run                # Check without saving
  python clean_data.py --report                 # Show cleaning report
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

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
BASE_DIR       = Path(__file__).resolve().parent.parent
RAW_DIR        = BASE_DIR / "raw"
PROCESSED_DIR  = BASE_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# VALIDATION RULES
# ─────────────────────────────────────────────
# Water level must be between these values (meters)
# Less than 0.5m = sensor error, more than 150m = unrealistic
WATER_LEVEL_MIN = 0.5
WATER_LEVEL_MAX = 150.0

# Max allowed jump between readings (meters per 6 hours)
# More than 5m change in 6 hours = sensor spike
MAX_LEVEL_JUMP  = 5.0

# Required columns in stations file
REQUIRED_STATION_COLS = [
    "station_id", "station_name", "state",
    "district", "latitude", "longitude",
]

# Required columns in readings file
REQUIRED_READINGS_COLS = [
    "station_id", "timestamp", "water_level_m",
]


# ═══════════════════════════════════════════════════════════════
# STATION CLEANER
# ═══════════════════════════════════════════════════════════════
def clean_stations(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean station master data.
    Returns cleaned DataFrame + report of what was fixed.
    """
    report = {}
    original_count = len(df)
    log.info(f"Cleaning stations — {original_count} rows")

    # ── Step 1: Check required columns ──────────────────────────
    missing_cols = [c for c in REQUIRED_STATION_COLS if c not in df.columns]
    if missing_cols:
        log.warning(f"  Missing columns: {missing_cols} — adding empty")
        for col in missing_cols:
            df[col] = None

    # ── Step 2: Standardize column names ────────────────────────
    # lowercase, strip spaces
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # ── Step 3: Remove duplicate station IDs ────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["station_id"], keep="first")
    dupes_removed = before - len(df)
    report["duplicate_stations_removed"] = dupes_removed
    if dupes_removed:
        log.info(f"  Removed {dupes_removed} duplicate station IDs")

    # ── Step 4: Drop rows with no station_id ────────────────────
    before = len(df)
    df = df.dropna(subset=["station_id"])
    df = df[df["station_id"].astype(str).str.strip() != ""]
    no_id_removed = before - len(df)
    report["no_id_removed"] = no_id_removed
    if no_id_removed:
        log.info(f"  Removed {no_id_removed} rows with empty station_id")

    # ── Step 5: Fix latitude / longitude ────────────────────────
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    # India bounding box — lat: 6-38, lon: 68-98
    invalid_coords = (
        (df["latitude"]  < 6)  | (df["latitude"]  > 38) |
        (df["longitude"] < 68) | (df["longitude"] > 98)
    )
    invalid_count = invalid_coords.sum()
    if invalid_count:
        log.warning(f"  {invalid_count} stations have coordinates outside India — setting to NaN")
        df.loc[invalid_coords, ["latitude", "longitude"]] = np.nan
    report["invalid_coords"] = int(invalid_count)

    # ── Step 6: Standardize state / district names ───────────────
    # Title case, strip spaces
    for col in ["state", "district", "block", "station_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()
            df[col] = df[col].replace("Nan", np.nan)

    # ── Step 7: Fix well depth ───────────────────────────────────
    if "well_depth_m" in df.columns:
        df["well_depth_m"] = pd.to_numeric(df["well_depth_m"], errors="coerce")
        # Well depth should be between 5m and 500m
        invalid_depth = (df["well_depth_m"] < 5) | (df["well_depth_m"] > 500)
        df.loc[invalid_depth, "well_depth_m"] = np.nan

    # ── Step 8: Standardize aquifer type ────────────────────────
    if "aquifer_type" in df.columns:
        aquifer_map = {
            "alluvial": "Alluvial",
            "hard rock": "Hard Rock",
            "hardrock": "Hard Rock",
            "basalt": "Basalt",
            "limestone": "Limestone",
            "sandstone": "Sandstone",
        }
        df["aquifer_type"] = (
            df["aquifer_type"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(aquifer_map)
            .fillna("Unknown")
        )

    # ── Step 9: Add cleaned timestamp ───────────────────────────
    df["cleaned_at"] = datetime.now().isoformat()

    report["original_count"]  = original_count
    report["final_count"]     = len(df)
    report["rows_removed"]    = original_count - len(df)

    log.info(f"  Stations cleaned: {original_count} → {len(df)}")
    return df, report


# ═══════════════════════════════════════════════════════════════
# READINGS CLEANER
# ═══════════════════════════════════════════════════════════════
def clean_readings(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean DWLR water level readings.
    Returns cleaned DataFrame + report of what was fixed.
    """
    report = {}
    original_count = len(df)
    log.info(f"Cleaning readings — {original_count} rows")

    if df.empty:
        log.warning("  Empty readings DataFrame — nothing to clean")
        return df, {"original_count": 0, "final_count": 0}

    # ── Step 1: Check required columns ──────────────────────────
    missing_cols = [c for c in REQUIRED_READINGS_COLS if c not in df.columns]
    if missing_cols:
        log.error(f"  CRITICAL: Missing required columns: {missing_cols}")
        return pd.DataFrame(), {"error": f"Missing columns: {missing_cols}"}

    # ── Step 2: Parse timestamps ─────────────────────────────────
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad_timestamps = df["timestamp"].isna().sum()
    if bad_timestamps:
        log.warning(f"  {bad_timestamps} unparseable timestamps — removing")
        df = df.dropna(subset=["timestamp"])
    report["bad_timestamps_removed"] = int(bad_timestamps)

    # ── Step 3: Remove future timestamps ────────────────────────
    now = datetime.now()
    future_mask = df["timestamp"] > now
    future_count = future_mask.sum()
    if future_count:
        log.warning(f"  {future_count} future timestamps found — removing")
        df = df[~future_mask]
    report["future_timestamps_removed"] = int(future_count)

    # ── Step 4: Parse water level as float ──────────────────────
    df["water_level_m"] = pd.to_numeric(df["water_level_m"], errors="coerce")

    # ── Step 5: Remove physically impossible values ──────────────
    before = len(df)
    invalid_wl = (
        (df["water_level_m"] < WATER_LEVEL_MIN) |
        (df["water_level_m"] > WATER_LEVEL_MAX) |
        df["water_level_m"].isna()
    )
    df = df[~invalid_wl]
    impossible_removed = before - len(df)
    report["impossible_values_removed"] = impossible_removed
    if impossible_removed:
        log.info(f"  Removed {impossible_removed} impossible water level values")

    # ── Step 6: Remove duplicates ────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["station_id", "timestamp"], keep="first")
    dupes_removed = before - len(df)
    report["duplicate_readings_removed"] = dupes_removed
    if dupes_removed:
        log.info(f"  Removed {dupes_removed} duplicate readings")

    # ── Step 7: Remove suspect quality readings ──────────────────
    if "data_quality" in df.columns:
        before = len(df)
        df = df[df["data_quality"].str.lower() != "bad"]
        suspect_removed = before - len(df)
        report["bad_quality_removed"] = suspect_removed
        if suspect_removed:
            log.info(f"  Removed {suspect_removed} bad quality readings")

    # ── Step 8: Detect and remove sensor spikes ──────────────────
    # A spike = water level jumps more than MAX_LEVEL_JUMP in one step
    df = df.sort_values(["station_id", "timestamp"])
    df["prev_level"] = df.groupby("station_id")["water_level_m"].shift(1)
    df["level_jump"] = (df["water_level_m"] - df["prev_level"]).abs()

    before = len(df)
    spikes = (df["level_jump"] > MAX_LEVEL_JUMP) & df["prev_level"].notna()
    df = df[~spikes]
    spikes_removed = before - len(df)
    report["spikes_removed"] = spikes_removed
    if spikes_removed:
        log.info(f"  Removed {spikes_removed} sensor spike readings")

    # Drop helper columns
    df = df.drop(columns=["prev_level", "level_jump"])

    # ── Step 9: Sort and add cleaned timestamp ───────────────────
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    df["cleaned_at"] = datetime.now().isoformat()

    report["original_count"] = original_count
    report["final_count"]    = len(df)
    report["rows_removed"]   = original_count - len(df)
    report["retention_pct"]  = round((len(df) / original_count) * 100, 1) if original_count else 0

    log.info(f"  Readings cleaned: {original_count} → {len(df)} ({report['retention_pct']}% retained)")
    return df, report


# ═══════════════════════════════════════════════════════════════
# SAVE — Write to processed/
# ═══════════════════════════════════════════════════════════════
def save_processed(df: pd.DataFrame, filename: str, dry_run: bool = False) -> Path:
    """Save cleaned DataFrame to processed/ folder."""
    if df.empty:
        log.warning(f"  Nothing to save for {filename}")
        return None

    filepath = PROCESSED_DIR / filename

    if dry_run:
        log.info(f"  [DRY RUN] Would save {len(df)} rows → {filepath}")
        return filepath

    df.to_csv(filepath, index=False)
    log.info(f"  Saved {len(df)} rows → {filepath}")
    return filepath


# ═══════════════════════════════════════════════════════════════
# REPORT PRINTER
# ═══════════════════════════════════════════════════════════════
def print_report(stations_report: dict, readings_report: dict):
    """Print a human-readable cleaning summary."""
    print("\n" + "=" * 55)
    print("  SubTerra — Data Cleaning Report")
    print("=" * 55)

    print("\n📍 STATIONS")
    print(f"  Original rows     : {stations_report.get('original_count', 0)}")
    print(f"  Duplicates removed: {stations_report.get('duplicate_stations_removed', 0)}")
    print(f"  No ID removed     : {stations_report.get('no_id_removed', 0)}")
    print(f"  Invalid coords    : {stations_report.get('invalid_coords', 0)}")
    print(f"  Final rows        : {stations_report.get('final_count', 0)}")

    print("\n📊 READINGS")
    print(f"  Original rows     : {readings_report.get('original_count', 0)}")
    print(f"  Bad timestamps    : {readings_report.get('bad_timestamps_removed', 0)}")
    print(f"  Future timestamps : {readings_report.get('future_timestamps_removed', 0)}")
    print(f"  Impossible values : {readings_report.get('impossible_values_removed', 0)}")
    print(f"  Duplicates        : {readings_report.get('duplicate_readings_removed', 0)}")
    print(f"  Bad quality       : {readings_report.get('bad_quality_removed', 0)}")
    print(f"  Sensor spikes     : {readings_report.get('spikes_removed', 0)}")
    print(f"  Final rows        : {readings_report.get('final_count', 0)}")
    print(f"  Retention         : {readings_report.get('retention_pct', 0)}%")
    print("=" * 55 + "\n")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="SubTerra Data Cleaner — cleans raw DWLR data"
    )
    parser.add_argument("--input",   type=str, default=str(RAW_DIR),
                        help="Input folder (default: data/raw/)")
    parser.add_argument("--output",  type=str, default=str(PROCESSED_DIR),
                        help="Output folder (default: data/processed/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check data without saving anything")
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

    # ── Load raw files ───────────────────────────────────────────
    stations_file = input_dir / "stations_latest.csv"
    readings_file = input_dir / "readings_latest.csv"

    if not stations_file.exists():
        log.error(f"stations_latest.csv not found in {input_dir}")
        log.error("Run scraper.py first to generate raw data")
        return

    if not readings_file.exists():
        log.error(f"readings_latest.csv not found in {input_dir}")
        log.error("Run scraper.py first to generate raw data")
        return

    stations_raw = pd.read_csv(stations_file)
    readings_raw = pd.read_csv(readings_file, parse_dates=["timestamp"])

    log.info(f"Loaded {len(stations_raw)} stations, {len(readings_raw)} readings")

    # ── Clean ────────────────────────────────────────────────────
    stations_clean, stations_report = clean_stations(stations_raw)
    readings_clean, readings_report = clean_readings(readings_raw)

    # ── Save ─────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    save_processed(stations_clean, f"stations_{timestamp}.csv",  args.dry_run)
    save_processed(readings_clean, f"readings_{timestamp}.csv",  args.dry_run)
    save_processed(stations_clean, "stations_latest.csv",        args.dry_run)
    save_processed(readings_clean, "readings_latest.csv",        args.dry_run)

    # ── Report ───────────────────────────────────────────────────
    if args.report or args.dry_run:
        print_report(stations_report, readings_report)

    log.info("Cleaning complete ✅")


if __name__ == "__main__":
    main()