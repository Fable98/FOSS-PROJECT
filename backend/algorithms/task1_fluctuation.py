"""
algorithms/task1_fluctuation.py — SubTerra
Task 1: Analyze Real-Time Water Level Fluctuations

Computes:
  - Rate of rise/fall per hour, day, week
  - Moving average trend (7-day)
  - Anomaly detection (sudden drops = over-extraction signal)
  - Seasonal pattern classification (pre/post monsoon)

Called by: app/services/analytics.py
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("subterra.task1")

# ── Constants ──────────────────────────────────────────────────────────────────
SUDDEN_DROP_THRESHOLD_M  = 2.0    # metres drop in one hour = over-extraction signal
MOVING_AVG_WINDOW_DAYS   = 7      # 7-day moving average window
READINGS_PER_HOUR        = 4      # 15-min interval = 4 readings/hr
READINGS_PER_DAY         = 96     # 4 * 24
READINGS_PER_WEEK        = 672    # 4 * 24 * 7

# Monsoon season definitions (India standard)
PRE_MONSOON_MONTHS  = [3, 4, 5, 6]     # Mar–Jun
MONSOON_MONTHS      = [7, 8, 9]        # Jul–Sep
POST_MONSOON_MONTHS = [10, 11]         # Oct–Nov
WINTER_MONTHS       = [12, 1, 2]       # Dec–Feb


# ═══════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════

def analyze_fluctuations(
    readings_df: pd.DataFrame,
    station_id: str,
) -> dict:
    """
    Full Task 1 analysis for a single station.

    Args:
        readings_df : DataFrame with columns:
                      station_id, timestamp, water_level_m,
                      data_quality_flag, is_anomaly
        station_id  : Station to analyse

    Returns dict with keys:
        station_id, rate_per_hour, rate_per_day, rate_per_week,
        trend_7day, current_level_m, anomalies, seasonal_phase,
        moving_average, status, summary
    """
    df = readings_df[readings_df["station_id"] == station_id].copy()

    if df.empty:
        log.warning(f"No readings found for station {station_id}")
        return _empty_result(station_id, "No data available")

    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[df["data_quality_flag"].isin(["G", "Good"]) | ~df["data_quality_flag"].isin(["E", "M", "X"])]

    if len(df) < 2:
        return _empty_result(station_id, "Insufficient readings")

    current_level = float(df["water_level_m"].iloc[-1])
    current_time  = df["timestamp"].iloc[-1]

    # Compute all metrics
    rates          = _compute_rates(df)
    trend          = _compute_trend(df)
    moving_avg     = _compute_moving_average(df)
    anomalies      = _detect_anomalies(df)
    seasonal_phase = _get_seasonal_phase(current_time)
    status         = _classify_trend_status(rates["per_day"], trend["direction"])

    result = {
        "station_id":      station_id,
        "current_level_m": round(current_level, 3),
        "as_of":           current_time.isoformat(),
        "rate_per_hour":   rates["per_hour"],
        "rate_per_day":    rates["per_day"],
        "rate_per_week":   rates["per_week"],
        "trend_direction": trend["direction"],       # "rising" | "falling" | "stable"
        "trend_magnitude": trend["magnitude"],       # absolute change over 7 days
        "moving_average":  moving_avg,
        "anomalies":       anomalies,
        "seasonal_phase":  seasonal_phase,
        "status":          status,
        "total_readings":  len(df),
        "summary":         _build_summary(station_id, current_level, rates, trend, anomalies),
    }

    log.info(
        f"Task1 [{station_id}] level={current_level}m "
        f"rate={rates['per_day']:+.3f}m/day trend={trend['direction']}"
    )
    return result


# ═══════════════════════════════════════════════════════════════
# RATE OF CHANGE
# ═══════════════════════════════════════════════════════════════

def _compute_rates(df: pd.DataFrame) -> dict:
    """
    Compute rate of water level change per hour, day, week.
    Positive = level rising (water table deepening — worsening)
    Negative = level falling (water table rising — improving)
    """
    def _rate_over_window(df, n_readings):
        if len(df) < n_readings:
            recent = df
        else:
            recent = df.tail(n_readings)
        if len(recent) < 2:
            return 0.0
        level_change = float(recent["water_level_m"].iloc[-1]) - \
                       float(recent["water_level_m"].iloc[0])
        return round(level_change, 4)

    return {
        "per_hour": _rate_over_window(df, READINGS_PER_HOUR),
        "per_day":  _rate_over_window(df, READINGS_PER_DAY),
        "per_week": _rate_over_window(df, READINGS_PER_WEEK),
    }


# ═══════════════════════════════════════════════════════════════
# TREND ANALYSIS
# ═══════════════════════════════════════════════════════════════

def _compute_trend(df: pd.DataFrame) -> dict:
    """
    Compute 7-day linear trend direction and magnitude.
    Uses linear regression on the last 7 days of readings.
    """
    window = df.tail(READINGS_PER_WEEK)
    if len(window) < 10:
        window = df

    x = np.arange(len(window))
    y = window["water_level_m"].values

    if len(x) < 2:
        return {"direction": "stable", "magnitude": 0.0, "slope": 0.0}

    # Linear regression slope
    slope = float(np.polyfit(x, y, 1)[0])

    # Scale slope to metres/day
    slope_per_day = slope * READINGS_PER_DAY

    if slope_per_day > 0.05:
        direction = "rising"      # water table deepening (bad)
    elif slope_per_day < -0.05:
        direction = "falling"     # water table recovering (good)
    else:
        direction = "stable"

    magnitude = round(abs(slope_per_day * 7), 3)   # total change over 7 days

    return {
        "direction": direction,
        "magnitude": magnitude,
        "slope":     round(slope_per_day, 5),
    }


# ═══════════════════════════════════════════════════════════════
# MOVING AVERAGE
# ═══════════════════════════════════════════════════════════════

def _compute_moving_average(df: pd.DataFrame) -> list[dict]:
    """
    Compute 7-day rolling average of water level.
    Returns last 30 data points for chart rendering.
    """
    df = df.copy()
    df["moving_avg_7d"] = (
        df["water_level_m"]
        .rolling(window=READINGS_PER_WEEK, min_periods=READINGS_PER_DAY)
        .mean()
        .round(3)
    )

    # Return last 30 daily averages for frontend charts
    daily = (
        df.set_index("timestamp")
        .resample("D")["water_level_m"]
        .mean()
        .round(3)
        .dropna()
        .tail(30)
        .reset_index()
    )

    return [
        {
            "date":          row["timestamp"].strftime("%Y-%m-%d"),
            "avg_level_m":   round(row["water_level_m"], 3),
        }
        for _, row in daily.iterrows()
    ]


# ═══════════════════════════════════════════════════════════════
# ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════

def _detect_anomalies(df: pd.DataFrame) -> list[dict]:
    """
    Detect anomalous readings:
      1. Sudden drops > SUDDEN_DROP_THRESHOLD_M in one hour
         → likely over-extraction event
      2. Statistical spikes already flagged by clean_data.py
         (is_anomaly = True)
    Returns list of anomaly events with timestamp and reason.
    """
    anomalies = []

    # Sudden drops (over-extraction signal)
    hourly = df.set_index("timestamp").resample("H")["water_level_m"].mean().reset_index()
    hourly["diff"] = hourly["water_level_m"].diff()
    drops = hourly[hourly["diff"] > SUDDEN_DROP_THRESHOLD_M]

    for _, row in drops.iterrows():
        anomalies.append({
            "timestamp":  row["timestamp"].isoformat(),
            "type":       "sudden_drop",
            "magnitude_m": round(float(row["diff"]), 3),
            "reason":     f"Water level rose {round(float(row['diff']), 2)}m in 1 hour — possible over-extraction",
        })

    # Statistical anomalies from cleaning pipeline
    if "is_anomaly" in df.columns:
        stat_anomalies = df[df["is_anomaly"] == True]
        for _, row in stat_anomalies.iterrows():
            anomalies.append({
                "timestamp":   pd.Timestamp(row["timestamp"]).isoformat(),
                "type":        "statistical",
                "magnitude_m": round(float(row["water_level_m"]), 3),
                "reason":      row.get("anomaly_reason", "statistical_anomaly"),
            })

    # Sort by timestamp descending, return most recent 20
    anomalies = sorted(anomalies, key=lambda x: x["timestamp"], reverse=True)[:20]
    return anomalies


# ═══════════════════════════════════════════════════════════════
# SEASONAL PHASE
# ═══════════════════════════════════════════════════════════════

def _get_seasonal_phase(dt: datetime) -> str:
    """Return current seasonal phase based on Indian monsoon calendar."""
    month = dt.month if hasattr(dt, "month") else pd.Timestamp(dt).month
    if month in PRE_MONSOON_MONTHS:
        return "pre_monsoon"
    elif month in MONSOON_MONTHS:
        return "monsoon"
    elif month in POST_MONSOON_MONTHS:
        return "post_monsoon"
    else:
        return "winter"


# ═══════════════════════════════════════════════════════════════
# STATUS CLASSIFIER
# ═══════════════════════════════════════════════════════════════

def _classify_trend_status(rate_per_day: float, direction: str) -> str:
    """
    Classify the trend as one of four status levels.
    Based on rate of change per day.
    """
    if direction == "rising" and rate_per_day > 0.5:
        return "critical_depletion"
    elif direction == "rising" and rate_per_day > 0.1:
        return "moderate_depletion"
    elif direction == "stable":
        return "stable"
    elif direction == "falling":
        return "recovering"
    else:
        return "stable"


# ═══════════════════════════════════════════════════════════════
# BATCH ANALYSIS (all stations)
# ═══════════════════════════════════════════════════════════════

def analyze_all_stations(readings_df: pd.DataFrame) -> list[dict]:
    """
    Run Task 1 analysis for all stations in the DataFrame.
    Returns a list of result dicts, one per station.
    """
    station_ids = readings_df["station_id"].unique().tolist()
    log.info(f"Task 1 batch analysis — {len(station_ids)} stations")

    results = []
    for sid in station_ids:
        try:
            result = analyze_fluctuations(readings_df, sid)
            results.append(result)
        except Exception as e:
            log.error(f"Task1 failed for {sid}: {e}")
            results.append(_empty_result(sid, str(e)))

    return results


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _build_summary(
    station_id: str,
    current_level: float,
    rates: dict,
    trend: dict,
    anomalies: list,
) -> str:
    direction_word = {
        "rising":  "deepening (worsening)",
        "falling": "recovering (improving)",
        "stable":  "stable",
    }.get(trend["direction"], "stable")

    anomaly_note = (
        f" {len(anomalies)} anomalous event(s) detected."
        if anomalies else ""
    )

    return (
        f"Station {station_id}: current water level {current_level}m. "
        f"Level is {direction_word} at {abs(rates['per_day']):.3f}m/day. "
        f"7-day change: {trend['magnitude']:.3f}m.{anomaly_note}"
    )


def _empty_result(station_id: str, reason: str) -> dict:
    return {
        "station_id":      station_id,
        "current_level_m": None,
        "as_of":           None,
        "rate_per_hour":   0.0,
        "rate_per_day":    0.0,
        "rate_per_week":   0.0,
        "trend_direction": "unknown",
        "trend_magnitude": 0.0,
        "moving_average":  [],
        "anomalies":       [],
        "seasonal_phase":  "unknown",
        "status":          "no_data",
        "total_readings":  0,
        "summary":         reason,
    }