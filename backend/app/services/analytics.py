"""
SubTerra — Task 1: Real-Time Water Level Fluctuation Analysis
backend/app/services/analytics.py

Analyses DWLR sensor readings to detect:
  - Rising / falling / stable trends
  - Rate of change (1h, 24h, 7d, 30d)
  - Anomalies — sudden drops or spikes
  - Seasonal patterns — pre vs post monsoon

Output key contract (consumed by alerts.py):
  "avg_daily_change_m"  → average rate of change per day (positive = deepening)
  "analysed_at"         → ISO timestamp string
  "current_level_m"     → current water level in metres
  "trend"               → "Declining" | "Recovering" | "Stable" | "Unknown"

Used by:
  GET /api/v1/task1/{station_id}
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from scipy import stats

from app.config import settings

log = logging.getLogger("subterra.analytics")

# ─────────────────────────────────────────────
# CONSTANTS — pulled from config
# ─────────────────────────────────────────────
DEFAULT_HOURS  = settings.TASK1_DEFAULT_HOURS    # 168 = 7 days
ALERT_LOOKBACK = settings.ALERT_LOOKBACK_HOURS   # 48 hours

# A change > this per 24h = anomaly (metres)
ANOMALY_THRESHOLD = 2.0

# Trend thresholds (metres per day)
# Higher number = deeper = worse for groundwater
DECLINING_THRESHOLD  =  0.05   # deepening faster than this = Declining
RECOVERING_THRESHOLD = -0.05   # rising faster than this    = Recovering

# Monsoon months (India)
PRE_MONSOON_MONTHS  = [3, 4, 5, 6]     # March – June
POST_MONSOON_MONTHS = [10, 11, 12]     # October – December

# Quality flags that pass through — everything else is excluded
PASS_FLAGS = {"G", "Good"}


# ═══════════════════════════════════════════════════════════════
# MAIN — Full fluctuation analysis for one station
# ═══════════════════════════════════════════════════════════════
def analyze_fluctuation(
    station_id: str,
    readings:   pd.DataFrame,
    hours:      int = DEFAULT_HOURS,
) -> dict:
    """
    Task 1 — Analyse water level fluctuations for a DWLR station.

    Args:
        station_id : DWLR station ID e.g. "CGWB_RJ_0001"
        readings   : DataFrame with columns [timestamp, water_level_m,
                     data_quality_flag (optional)]
        hours      : Hours of history to analyse (default 168 = 7 days)

    Returns:
        dict — see Output key contract in module docstring
    """
    log.info(f"[Task 1] Analysing fluctuations for {station_id}")

    if readings.empty:
        return _empty_result(station_id, "No readings available")

    # Sort, drop nulls, filter to this station
    df = (
        readings
        .sort_values("timestamp")
        .dropna(subset=["water_level_m"])
        .copy()
    )

    # Filter quality — defensively, even though clean_data.py already did this
    if "data_quality_flag" in df.columns:
        df = df[df["data_quality_flag"].isin(PASS_FLAGS)]

    if df.empty:
        return _empty_result(station_id, "No good-quality readings")

    # Normalise timestamps to UTC for consistent windowing
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")

    # Time window filter
    cutoff    = df["timestamp"].max() - timedelta(hours=hours)
    df_window = df[df["timestamp"] >= cutoff]

    if len(df_window) < 2:
        return _empty_result(station_id, "Insufficient data in time window")

    # ── Run all calculations ─────────────────────────────────
    current_level    = _current_level(df_window)
    changes          = _calculate_changes(df_window)
    trend            = _calculate_trend(df_window)
    anomalies        = _detect_anomalies(df_window)
    seasonal         = _seasonal_pattern(df)       # full history for seasonal
    fluctuation_rate = _fluctuation_rate(df_window)
    stats_sum        = _stats_summary(df_window)

    return {
        "station_id":            station_id,
        "task":                  "fluctuation_analysis",
        "analysed_at":           datetime.now(timezone.utc).isoformat(),
        "hours_analysed":        hours,
        "data_points":           len(df_window),

        # Current state
        "current_level_m":       round(current_level, 2),

        # Changes over time windows
        "change_1h_m":           changes.get("1h"),
        "change_24h_m":          changes.get("24h"),
        "change_7d_m":           changes.get("7d"),
        "change_30d_m":          changes.get("30d"),

        # Trend — "Declining" | "Recovering" | "Stable" | "Unknown"
        "trend":                 trend["direction"],
        "trend_slope_m_per_day": round(trend["slope"], 4),
        "trend_confidence":      round(trend["r_squared"], 2),

        # Anomalies
        "anomalies_detected":    len(anomalies),
        "anomalies":             anomalies,

        # Seasonal
        "seasonal":              seasonal,

        # Stats
        "avg_level_m":           stats_sum["mean"],
        "min_level_m":           stats_sum["min"],
        "max_level_m":           stats_sum["max"],
        "std_dev_m":             stats_sum["std"],

        # Key consumed by alerts.py — rate per day, positive = deepening
        "avg_daily_change_m":    round(fluctuation_rate, 4),
    }


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _current_level(df: pd.DataFrame) -> float:
    """Most recent water level reading."""
    return float(df.iloc[-1]["water_level_m"])


def _calculate_changes(df: pd.DataFrame) -> dict:
    """
    Water level change over 1h, 24h, 7d, 30d windows.
    Positive = level went deeper (worsening).
    Negative = level came up (recovering).
    """
    latest    = float(df.iloc[-1]["water_level_m"])
    latest_ts = df["timestamp"].max()

    windows = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}
    result  = {}

    for label, hrs in windows.items():
        cutoff  = latest_ts - timedelta(hours=hrs)
        past_df = df[df["timestamp"] <= cutoff]
        if not past_df.empty:
            past_level    = float(past_df.iloc[-1]["water_level_m"])
            result[label] = round(latest - past_level, 3)
        else:
            result[label] = None

    return result


def _calculate_trend(df: pd.DataFrame) -> dict:
    """
    Linear regression over all readings in the window.
    Returns slope (m/day), direction, R² confidence.
    """
    if len(df) < 3:
        return {"direction": "Unknown", "slope": 0.0, "r_squared": 0.0}

    t0 = df["timestamp"].min()
    x  = (df["timestamp"] - t0).dt.total_seconds() / 86400  # convert to days
    y  = df["water_level_m"].values

    slope, _, r_value, _, _ = stats.linregress(x, y)
    r_squared = r_value ** 2

    # Positive slope = deeper = Declining (bad)
    # Negative slope = shallower = Recovering (good)
    if slope > DECLINING_THRESHOLD:
        direction = "Declining"
    elif slope < RECOVERING_THRESHOLD:
        direction = "Recovering"
    else:
        direction = "Stable"

    return {
        "direction": direction,
        "slope":     float(slope),       # metres per day
        "r_squared": float(r_squared),   # 0 = no trend, 1 = perfect fit
    }


def _detect_anomalies(df: pd.DataFrame) -> list:
    """
    Flags readings where level changed > ANOMALY_THRESHOLD per 24h.
    Normalises by actual elapsed time so sparse data doesn't false-fire.
    Returns last 5 anomalies only (most recent first).
    """
    df = df.sort_values("timestamp").copy()
    df["prev_level"] = df["water_level_m"].shift(1)
    df["prev_time"]  = df["timestamp"].shift(1)
    df["hrs_diff"]   = (
        (df["timestamp"] - df["prev_time"])
        .dt.total_seconds() / 3600
    ).clip(lower=0.25)   # avoid division-by-zero for duplicate timestamps

    df["level_change"]   = (df["water_level_m"] - df["prev_level"]).abs()
    df["change_per_24h"] = df["level_change"] / df["hrs_diff"] * 24

    anomaly_rows = df[
        (df["change_per_24h"] > ANOMALY_THRESHOLD) &
        df["prev_level"].notna()
    ]

    anomalies = []
    for _, row in anomaly_rows.iterrows():
        ts = row["timestamp"]
        # isoformat() works on both tz-aware and naive timestamps
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        anomalies.append({
            "timestamp":      ts_str,
            "water_level_m":  round(float(row["water_level_m"]), 2),
            "change_m":       round(float(row["level_change"]),   2),
            "change_per_24h": round(float(row["change_per_24h"]), 2),
            "type": (
                "Sudden Drop"   # water table deepened fast
                if row["water_level_m"] > row["prev_level"]
                else "Sudden Rise"
            ),
        })

    # Most recent 5, newest first
    return list(reversed(anomalies[-5:]))


def _seasonal_pattern(df: pd.DataFrame) -> dict:
    """
    Compare pre-monsoon vs post-monsoon average water levels.
    Shows whether monsoon recharge is actually happening.
    Needs at least 1 full year of readings to be meaningful.
    """
    if df.empty:
        return {"available": False}

    df = df.copy()
    df["month"] = df["timestamp"].dt.month

    pre  = df[df["month"].isin(PRE_MONSOON_MONTHS)]["water_level_m"]
    post = df[df["month"].isin(POST_MONSOON_MONTHS)]["water_level_m"]

    if pre.empty or post.empty:
        return {
            "available": False,
            "note":      "Need at least 1 year of data for seasonal analysis",
        }

    pre_avg  = float(pre.mean())
    post_avg = float(post.mean())

    # Positive recovery = monsoon brought level up = good
    recovery = round(pre_avg - post_avg, 2)

    return {
        "available":           True,
        "pre_monsoon_avg_m":   round(pre_avg,  2),
        "post_monsoon_avg_m":  round(post_avg, 2),
        "seasonal_recovery_m": recovery,
        "monsoon_recharged":   recovery > 0.1,
        "recharge_sufficient": recovery > 1.0,   # 1m+ = healthy
    }


def _fluctuation_rate(df: pd.DataFrame) -> float:
    """
    Average daily change rate over the analysis window.
    Positive = deepening (bad). Negative = recovering (good).
    Divides by actual elapsed days — not row count.
    """
    if len(df) < 2:
        return 0.0

    total_days = (
        (df["timestamp"].max() - df["timestamp"].min())
        .total_seconds() / 86400
    )
    if total_days == 0:
        return 0.0

    total_change = (
        float(df.iloc[-1]["water_level_m"]) -
        float(df.iloc[0]["water_level_m"])
    )
    return total_change / total_days


def _stats_summary(df: pd.DataFrame) -> dict:
    """Basic descriptive stats over the analysis window."""
    wl = df["water_level_m"]
    return {
        "mean": round(float(wl.mean()), 2),
        "min":  round(float(wl.min()),  2),
        "max":  round(float(wl.max()),  2),
        "std":  round(float(wl.std()),  2),
    }


def _empty_result(station_id: str, reason: str) -> dict:
    return {
        "station_id":         station_id,
        "task":               "fluctuation_analysis",
        "error":              reason,
        "analysed_at":        datetime.now(timezone.utc).isoformat(),
        "current_level_m":    None,
        "avg_daily_change_m": 0.0,
        "trend":              "Unknown",
    }