"""
test_pipeline.py — SubTerra Phase 1 Tests
Run with: pytest data/scripts/test_pipeline.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Make sure scripts/ is on the path when running from repo root
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from clean_data import (
    clean_readings,
    clean_stations,
    clean_rainfall,
    detect_anomalies,
    WATER_LEVEL_MIN,
    WATER_LEVEL_MAX,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_readings():
    return pd.DataFrame({
        "station_id":        ["S1", "S1", "S1", "S2", "S2"],
        "timestamp":         [
            "2025-06-01 00:00:00+05:30",
            "2025-06-01 00:15:00+05:30",
            "2025-06-01 00:15:00+05:30",   # duplicate
            "2025-06-01 00:00:00+05:30",
            "2025-06-01 00:15:00+05:30",
        ],
        "water_level_m":     [10.0, 10.2, 10.2, 999.0, 25.0],
        "data_quality_flag": ["G",  "G",  "G",  "E",   "G"],
    })


@pytest.fixture
def sample_stations():
    return pd.DataFrame({
        "station_id":   ["S1", "S2", "S3", "S_BAD"],
        "station_name": ["Alpha", "Beta", None, "OutOfBounds"],
        "latitude":     [26.9, 18.5, 12.9, 999.0],
        "longitude":    [75.7, 73.8, 77.5, 999.0],
        "state":        ["Rajasthan", "Maharashtra", "Karnataka", "Invalid"],
        "district":     ["Jaipur", "Pune", "Bangalore Rural", "Nowhere"],
        "block":        ["Amer", "Haveli", "Hosakote", "X"],
        "well_depth_m": [45.0, 38.5, 90.0, None],
        "aquifer_type": ["Alluvial", "Basalt", "Granite", None],
    })


@pytest.fixture
def sample_rainfall():
    return pd.DataFrame({
        "state":        ["Rajasthan", "Maharashtra", "Maharashtra"],
        "district":     ["Jaipur",    "Pune",         "Pune"],
        "date":         ["2025-06-01", "2025-06-01",  "2025-06-01"],  # duplicate
        "rainfall_mm":  [0.0,          12.4,          -5.0],          # negative invalid
    })


# ── Readings Tests ─────────────────────────────────────────────────────────────

class TestCleanReadings:

    def test_removes_bad_quality_flags(self, sample_readings):
        result = clean_readings(sample_readings)
        assert "S2" not in result["station_id"].values or \
               result[result["station_id"] == "S2"]["water_level_m"].isna().all()

    def test_removes_duplicates(self, sample_readings):
        result = clean_readings(sample_readings)
        dupes = result[result["station_id"] == "S1"].duplicated(
            subset=["station_id", "timestamp"]
        )
        assert not dupes.any()

    def test_out_of_range_flagged_as_suspect(self, sample_readings):
        # Inject a clearly out-of-range value for a Good-flagged reading
        df = sample_readings.copy()
        df.loc[4, "data_quality_flag"] = "G"     # S2 second row, override to Good
        df.loc[4, "water_level_m"] = 999.0
        result = clean_readings(df)
        suspect = result[result["data_quality_flag"] == "S"]
        assert not suspect.empty or result[result["water_level_m"] == 999].empty

    def test_timestamps_are_timezone_aware(self, sample_readings):
        result = clean_readings(sample_readings)
        assert result["timestamp"].dt.tz is not None

    def test_sorted_by_station_and_time(self, sample_readings):
        result = clean_readings(sample_readings)
        assert result["station_id"].is_monotonic_increasing or \
               result.equals(result.sort_values(["station_id", "timestamp"]).reset_index(drop=True))


class TestDetectAnomalies:

    def test_sudden_drop_flagged(self):
        rows = []
        base_time = pd.Timestamp("2025-01-01 00:00:00", tz="Asia/Kolkata")
        for i in range(20):
            rows.append({
                "station_id":        "S1",
                "timestamp":         base_time + pd.Timedelta(minutes=15*i),
                "water_level_m":     10.0,
                "data_quality_flag": "G",
            })
        # Inject a sudden drop of 10m
        rows.append({
            "station_id":        "S1",
            "timestamp":         base_time + pd.Timedelta(minutes=15*20),
            "water_level_m":     20.0,   # 10m drop in 15 min
            "data_quality_flag": "G",
        })
        df = pd.DataFrame(rows)
        result = detect_anomalies(df)
        assert result["is_anomaly"].any()


# ── Station Tests ──────────────────────────────────────────────────────────────

class TestCleanStations:

    def test_removes_out_of_bounds_stations(self, sample_stations):
        result = clean_stations(sample_stations)
        assert "S_BAD" not in result["station_id"].values

    def test_removes_null_lat_lon(self, sample_stations):
        df = sample_stations.copy()
        df.loc[0, "latitude"] = None
        result = clean_stations(df)
        assert "S1" not in result["station_id"].values

    def test_no_duplicate_station_ids(self, sample_stations):
        result = clean_stations(sample_stations)
        assert result["station_id"].is_unique

    def test_unknown_aquifer_filled(self, sample_stations):
        result = clean_stations(sample_stations)
        assert result["aquifer_type"].notna().all()


# ── Rainfall Tests ─────────────────────────────────────────────────────────────

class TestCleanRainfall:

    def test_removes_duplicates(self, sample_rainfall):
        result = clean_rainfall(sample_rainfall)
        assert len(result) == 2   # Jaipur + Pune (one Pune kept)

    def test_negative_rainfall_clamped_to_zero(self, sample_rainfall):
        result = clean_rainfall(sample_rainfall)
        assert (result["rainfall_mm"] >= 0).all()

    def test_date_parsed(self, sample_rainfall):
        result = clean_rainfall(sample_rainfall)
        assert hasattr(result["date"].iloc[0], "year")