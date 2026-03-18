"""
algorithms/task3_evaluation.py — SubTerra
Task 3: Evaluate Groundwater Resources in Real Time

Computes:
  - Zone classification: Safe / Semi-Critical / Critical / Over-Exploited
  - Years to depletion per station
  - District and state-level health scorecards
  - Real-time resource availability index

CGWB Classification Standard:
  Safe          : level < 8m,  development < 70%
  Semi-Critical : level 8–15m, development 70–90%
  Critical      : level 15–25m, development 90–100%
  Over-Exploited: level > 25m,  development > 100%

Called by: app/services/alerts.py and routes
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("subterra.task3")

# ── CGWB Classification Thresholds (metres) ────────────────────────────────────
SAFE_MAX           =  8.0
SEMI_CRITICAL_MAX  = 15.0
CRITICAL_MAX       = 25.0
# > 25m = Over-Exploited

# Stage of development thresholds (%)
SAFE_STAGE_MAX           = 70.0
SEMI_CRITICAL_STAGE_MAX  = 90.0
CRITICAL_STAGE_MAX       = 100.0

# Minimum readings required for depletion rate calculation
MIN_READINGS_FOR_DEPLETION = 30

# Status codes with display properties
STATUS_CONFIG = {
    "safe":           {"label": "Safe",           "color": "#27AE60", "priority": 1},
    "semi_critical":  {"label": "Semi-Critical",  "color": "#F39C12", "priority": 2},
    "critical":       {"label": "Critical",        "color": "#E74C3C", "priority": 3},
    "over_exploited": {"label": "Over-Exploited",  "color": "#2C3E50", "priority": 4},
    "unknown":        {"label": "Unknown",          "color": "#95A5A6", "priority": 0},
}


# ═══════════════════════════════════════════════════════════════
# MAIN EVALUATION FUNCTION
# ═══════════════════════════════════════════════════════════════

def evaluate_station(
    readings_df:    pd.DataFrame,
    station_meta:   dict,
    stage_of_dev:   Optional[float] = None,
) -> dict:
    """
    Full Task 3 evaluation for a single station.

    Args:
        readings_df   : DWLR readings with timestamp and water_level_m
        station_meta  : Dict with station_id, state, district, well_depth_m, aquifer_type
        stage_of_dev  : Stage of groundwater development (%) from CGWB block report

    Returns dict with keys:
        station_id, current_level_m, status, status_label, status_color,
        years_to_depletion, annual_depletion_rate_m,
        stage_of_development, historical_trend,
        resource_availability_index, alert_required, summary
    """
    station_id = station_meta.get("station_id", "unknown")
    df = readings_df[readings_df["station_id"] == station_id].copy()

    if df.empty:
        return _empty_result(station_id, "No readings available")

    df = df.sort_values("timestamp").reset_index(drop=True)

    current_level     = float(df["water_level_m"].iloc[-1])
    current_time      = pd.Timestamp(df["timestamp"].iloc[-1])

    # Core computations
    status            = _classify_status(current_level, stage_of_dev)
    depletion         = _compute_depletion_rate(df)
    years_to_depletion = _compute_years_to_depletion(
        current_level,
        station_meta.get("well_depth_m"),
        depletion["annual_rate_m"],
    )
    historical_trend  = _compute_historical_trend(df)
    rai               = _compute_resource_availability_index(
        current_level, stage_of_dev, depletion["annual_rate_m"]
    )
    alert_required    = status in ("critical", "over_exploited")

    result = {
        "station_id":                 station_id,
        "state":                      station_meta.get("state", ""),
        "district":                   station_meta.get("district", ""),
        "block":                      station_meta.get("block", ""),
        "aquifer_type":               station_meta.get("aquifer_type", "Unknown"),
        "current_level_m":            round(current_level, 3),
        "as_of":                      current_time.isoformat(),
        "status":                     status,
        "status_label":               STATUS_CONFIG[status]["label"],
        "status_color":               STATUS_CONFIG[status]["color"],
        "stage_of_development_pct":   stage_of_dev,
        "annual_depletion_rate_m":    depletion["annual_rate_m"],
        "years_to_depletion":         years_to_depletion,
        "historical_trend":           historical_trend,
        "resource_availability_index": rai,
        "alert_required":             alert_required,
        "summary":                    _build_summary(
            station_id, current_level, status, years_to_depletion, rai
        ),
    }

    log.info(
        f"Task3 [{station_id}] level={current_level}m "
        f"status={status} RAI={rai} alert={alert_required}"
    )
    return result


# ═══════════════════════════════════════════════════════════════
# STATUS CLASSIFICATION (CGWB Standard)
# ═══════════════════════════════════════════════════════════════

def _classify_status(
    current_level_m: float,
    stage_of_dev:    Optional[float],
) -> str:
    """
    Classify groundwater status using CGWB standard.
    Water level takes priority; stage_of_dev used as secondary indicator.
    """
    # Primary: water level depth
    if current_level_m <= SAFE_MAX:
        level_status = "safe"
    elif current_level_m <= SEMI_CRITICAL_MAX:
        level_status = "semi_critical"
    elif current_level_m <= CRITICAL_MAX:
        level_status = "critical"
    else:
        level_status = "over_exploited"

    if stage_of_dev is None:
        return level_status

    # Secondary: stage of development (escalate if both indicators agree)
    if stage_of_dev <= SAFE_STAGE_MAX:
        stage_status = "safe"
    elif stage_of_dev <= SEMI_CRITICAL_STAGE_MAX:
        stage_status = "semi_critical"
    elif stage_of_dev <= CRITICAL_STAGE_MAX:
        stage_status = "critical"
    else:
        stage_status = "over_exploited"

    # Return the worse of the two indicators
    priority = STATUS_CONFIG
    return (
        level_status
        if priority[level_status]["priority"] >= priority[stage_status]["priority"]
        else stage_status
    )


# ═══════════════════════════════════════════════════════════════
# DEPLETION RATE
# ═══════════════════════════════════════════════════════════════

def _compute_depletion_rate(df: pd.DataFrame) -> dict:
    """
    Compute annual depletion rate using linear regression on all available data.
    Positive = water table deepening (depleting).
    Negative = water table recovering.
    """
    if len(df) < MIN_READINGS_FOR_DEPLETION:
        return {"annual_rate_m": 0.0, "confidence": "low"}

    x = np.arange(len(df))
    y = df["water_level_m"].values

    slope = float(np.polyfit(x, y, 1)[0])

    # Convert slope (per reading) to annual rate (365 * 96 readings/year)
    readings_per_year = 365 * 96
    annual_rate = round(slope * readings_per_year, 3)

    confidence = "high" if len(df) > 1000 else "medium" if len(df) > 100 else "low"

    return {
        "annual_rate_m": annual_rate,
        "confidence":    confidence,
    }


# ═══════════════════════════════════════════════════════════════
# YEARS TO DEPLETION
# ═══════════════════════════════════════════════════════════════

def _compute_years_to_depletion(
    current_level_m:   float,
    well_depth_m:      Optional[float],
    annual_depletion:  float,
) -> Optional[float]:
    """
    Estimate years until well runs dry at current depletion rate.
    Returns None if recovering, or if well depth unknown.
    """
    if annual_depletion <= 0:
        return None   # recovering — no depletion

    if not well_depth_m:
        # Without well depth, estimate based on CGWB over-exploited threshold
        remaining = max(0, 25.0 - current_level_m)
    else:
        remaining = max(0, float(well_depth_m) - current_level_m)

    if remaining <= 0:
        return 0.0

    years = round(remaining / annual_depletion, 1)
    return years


# ═══════════════════════════════════════════════════════════════
# HISTORICAL TREND (5–10 year)
# ═══════════════════════════════════════════════════════════════

def _compute_historical_trend(df: pd.DataFrame) -> dict:
    """
    Analyse long-term trend using annual averages.
    Returns yearly average water levels for chart rendering.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["year"]      = df["timestamp"].dt.year

    yearly = (
        df.groupby("year")["water_level_m"]
        .mean()
        .round(3)
        .reset_index()
        .rename(columns={"water_level_m": "avg_level_m"})
    )

    if len(yearly) < 2:
        return {"data": yearly.to_dict(orient="records"), "long_term_direction": "insufficient_data"}

    # Overall trend direction
    first_year_avg = float(yearly["avg_level_m"].iloc[0])
    last_year_avg  = float(yearly["avg_level_m"].iloc[-1])
    total_change   = last_year_avg - first_year_avg

    if total_change > 1.0:
        direction = "long_term_depletion"
    elif total_change < -1.0:
        direction = "long_term_recovery"
    else:
        direction = "long_term_stable"

    return {
        "data":                  yearly.to_dict(orient="records"),
        "long_term_direction":   direction,
        "total_change_m":        round(total_change, 3),
        "years_of_data":         len(yearly),
    }


# ═══════════════════════════════════════════════════════════════
# RESOURCE AVAILABILITY INDEX (RAI)
# ═══════════════════════════════════════════════════════════════

def _compute_resource_availability_index(
    current_level_m:  float,
    stage_of_dev:     Optional[float],
    annual_depletion: float,
) -> float:
    """
    Composite index from 0 (worst) to 100 (best).
    Combines: current status, stage of development, depletion rate.
    Used for district ranking.
    """
    # Component 1: level score (0–40 points)
    if current_level_m <= SAFE_MAX:
        level_score = 40.0
    elif current_level_m <= SEMI_CRITICAL_MAX:
        level_score = 40 * (1 - (current_level_m - SAFE_MAX) / (SEMI_CRITICAL_MAX - SAFE_MAX)) * 0.7 + 12
    elif current_level_m <= CRITICAL_MAX:
        level_score = 12 * (1 - (current_level_m - SEMI_CRITICAL_MAX) / (CRITICAL_MAX - SEMI_CRITICAL_MAX)) * 0.5 + 2
    else:
        level_score = max(0, 2 - (current_level_m - CRITICAL_MAX) * 0.1)

    # Component 2: stage of development score (0–35 points)
    if stage_of_dev is None:
        stage_score = 17.5  # neutral
    elif stage_of_dev <= SAFE_STAGE_MAX:
        stage_score = 35.0
    elif stage_of_dev <= SEMI_CRITICAL_STAGE_MAX:
        stage_score = 35 * (1 - (stage_of_dev - SAFE_STAGE_MAX) / 20) * 0.5 + 5
    elif stage_of_dev <= CRITICAL_STAGE_MAX:
        stage_score = 5 * (1 - (stage_of_dev - SEMI_CRITICAL_STAGE_MAX) / 10) * 0.5
    else:
        stage_score = 0.0

    # Component 3: depletion rate score (0–25 points)
    if annual_depletion <= 0:
        depletion_score = 25.0   # recovering
    elif annual_depletion < 0.5:
        depletion_score = 25 * (1 - annual_depletion / 0.5) * 0.7 + 7.5
    elif annual_depletion < 1.0:
        depletion_score = 7.5 * (1 - (annual_depletion - 0.5) / 0.5)
    else:
        depletion_score = 0.0

    rai = round(level_score + stage_score + depletion_score, 1)
    return min(100.0, max(0.0, rai))


# ═══════════════════════════════════════════════════════════════
# DISTRICT SCORECARD
# ═══════════════════════════════════════════════════════════════

def generate_district_scorecard(station_results: list[dict]) -> dict:
    """
    Aggregate station-level Task 3 results into a district scorecard.
    Called by GET /api/summary/{state}/{district}
    """
    if not station_results:
        return {"error": "No station data"}

    df = pd.DataFrame(station_results)

    status_counts = df["status"].value_counts().to_dict()
    avg_rai       = round(float(df["resource_availability_index"].mean()), 1)
    avg_level     = round(float(df["current_level_m"].dropna().mean()), 3)
    alert_count   = int(df["alert_required"].sum())

    # District-level status = worst station status
    priority_map  = {v["label"]: v["priority"] for v in STATUS_CONFIG.values()}
    worst_status  = df.loc[df["status"].map(
        {k: v["priority"] for k, v in STATUS_CONFIG.items()}
    ).fillna(0).idxmax(), "status"]

    # Ranking within district
    df_ranked = df.nsmallest(5, "resource_availability_index")[
        ["station_id", "current_level_m", "status", "resource_availability_index"]
    ]

    return {
        "total_stations":        len(df),
        "district_status":       worst_status,
        "avg_resource_index":    avg_rai,
        "avg_water_level_m":     avg_level,
        "status_breakdown":      status_counts,
        "alerts_active":         alert_count,
        "most_stressed_stations": df_ranked.to_dict(orient="records"),
    }


def generate_state_scorecard(district_scorecards: dict) -> dict:
    """
    Aggregate district scorecards into a state-level summary.
    Called by GET /api/summary/{state}
    """
    if not district_scorecards:
        return {"error": "No district data"}

    all_statuses  = []
    all_rai       = []
    total_alerts  = 0
    total_stations = 0

    for district, card in district_scorecards.items():
        all_statuses.append(card.get("district_status", "unknown"))
        all_rai.append(card.get("avg_resource_index", 50))
        total_alerts   += card.get("alerts_active", 0)
        total_stations += card.get("total_stations", 0)

    status_counts = pd.Series(all_statuses).value_counts().to_dict()

    return {
        "total_districts":   len(district_scorecards),
        "total_stations":    total_stations,
        "avg_resource_index": round(float(np.mean(all_rai)), 1),
        "total_alerts":      total_alerts,
        "status_breakdown":  status_counts,
        "district_ranking":  sorted(
            [{"district": d, "rai": district_scorecards[d].get("avg_resource_index", 0)}
             for d in district_scorecards],
            key=lambda x: x["rai"]
        ),
    }


# ═══════════════════════════════════════════════════════════════
# BATCH EVALUATION
# ═══════════════════════════════════════════════════════════════

def evaluate_all_stations(
    readings_df:  pd.DataFrame,
    stations_df:  pd.DataFrame,
    stage_map:    dict = None,
) -> list[dict]:
    """
    Run Task 3 evaluation for all stations.
    stage_map: {station_id: stage_of_development_pct}
    """
    log.info(f"Task 3 batch evaluation — {len(stations_df)} stations")
    results = []
    for _, station in stations_df.iterrows():
        sid   = station.get("station_id")
        stage = (stage_map or {}).get(sid)
        try:
            result = evaluate_station(readings_df, station.to_dict(), stage)
            results.append(result)
        except Exception as e:
            log.error(f"Task3 failed for {sid}: {e}")
            results.append(_empty_result(sid, str(e)))
    return results


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _build_summary(
    station_id:        str,
    current_level:     float,
    status:            str,
    years_to_depletion: Optional[float],
    rai:               float,
) -> str:
    depletion_str = (
        f" At current rate, well may deplete in {years_to_depletion} years."
        if years_to_depletion is not None and years_to_depletion < 50
        else ""
    )
    return (
        f"Station {station_id}: water level {current_level}m — "
        f"{STATUS_CONFIG[status]['label']}. "
        f"Resource Availability Index: {rai}/100.{depletion_str}"
    )


def _empty_result(station_id: str, reason: str) -> dict:
    return {
        "station_id":                  station_id,
        "state":                       "",
        "district":                    "",
        "block":                       "",
        "aquifer_type":                "Unknown",
        "current_level_m":             None,
        "as_of":                       None,
        "status":                      "unknown",
        "status_label":                "Unknown",
        "status_color":                "#95A5A6",
        "stage_of_development_pct":    None,
        "annual_depletion_rate_m":     0.0,
        "years_to_depletion":          None,
        "historical_trend":            {"data": [], "long_term_direction": "unknown"},
        "resource_availability_index": 0.0,
        "alert_required":              False,
        "summary":                     reason,
    }