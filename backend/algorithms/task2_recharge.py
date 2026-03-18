"""
algorithms/task2_recharge.py — SubTerra
Task 2: Estimate Recharge Dynamically

Computes:
  - Recharge rate (metres/day after rainfall event)
  - Recharge lag time (hours between rainfall and water level response)
  - Net recharge (post-monsoon level minus pre-monsoon level)
  - Zones with zero or negative recharge (critically stressed)

Called by: app/services/recharge.py
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("subterra.task2")

# ── Constants ──────────────────────────────────────────────────────────────────
MIN_RAINFALL_EVENT_MM    = 10.0   # minimum rainfall to trigger recharge check
RECHARGE_WINDOW_HOURS    = 72     # hours after rainfall to look for water level response
MAX_LAG_HOURS            = 48     # maximum expected lag between rain and response
PRE_MONSOON_MONTHS       = [5, 6]
POST_MONSOON_MONTHS      = [10, 11]


# ═══════════════════════════════════════════════════════════════
# MAIN ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════

def estimate_recharge(
    readings_df:  pd.DataFrame,
    rainfall_df:  pd.DataFrame,
    station_meta: dict,
) -> dict:
    """
    Full Task 2 recharge analysis for a single station.

    Args:
        readings_df  : DWLR readings (station_id, timestamp, water_level_m)
        rainfall_df  : District rainfall (state, district, date, rainfall_mm)
        station_meta : Dict with station_id, state, district, aquifer_type, well_depth_m

    Returns dict with keys:
        station_id, recharge_rate_m_per_day, lag_hours,
        net_recharge_m, pre_monsoon_level_m, post_monsoon_level_m,
        recharge_events, zone_status, aquifer_type, summary
    """
    station_id   = station_meta.get("station_id", "unknown")
    aquifer_type = station_meta.get("aquifer_type", "Unknown")
    district     = station_meta.get("district", "")
    state        = station_meta.get("state", "")

    df = readings_df[readings_df["station_id"] == station_id].copy()
    rf = rainfall_df[
        (rainfall_df["state"].str.lower()    == state.lower()) &
        (rainfall_df["district"].str.lower() == district.lower())
    ].copy()

    if df.empty:
        return _empty_result(station_id, "No readings available")

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Core computations
    recharge_events = _detect_recharge_events(df, rf)
    recharge_rate   = _compute_recharge_rate(recharge_events)
    lag_hours       = _compute_lag_time(recharge_events)
    net_recharge    = _compute_net_recharge(df)
    zone_status     = _classify_recharge_zone(
        net_recharge["net_recharge_m"], recharge_rate, aquifer_type
    )

    result = {
        "station_id":             station_id,
        "aquifer_type":           aquifer_type,
        "recharge_rate_m_per_day": recharge_rate,
        "lag_hours":              lag_hours,
        "net_recharge_m":         net_recharge["net_recharge_m"],
        "pre_monsoon_level_m":    net_recharge["pre_monsoon_level_m"],
        "post_monsoon_level_m":   net_recharge["post_monsoon_level_m"],
        "recharge_events":        recharge_events[:10],   # last 10 events
        "recharge_capacity_m":    _compute_recharge_capacity(df, station_meta),
        "zone_status":            zone_status,
        "summary":                _build_summary(
            station_id, recharge_rate, net_recharge, zone_status, aquifer_type
        ),
    }

    log.info(
        f"Task2 [{station_id}] rate={recharge_rate}m/day "
        f"net={net_recharge['net_recharge_m']}m zone={zone_status}"
    )
    return result


# ═══════════════════════════════════════════════════════════════
# RECHARGE EVENT DETECTION
# ═══════════════════════════════════════════════════════════════

def _detect_recharge_events(
    df: pd.DataFrame,
    rf: pd.DataFrame,
) -> list[dict]:
    """
    Detect individual recharge events by correlating rainfall with
    subsequent water level recovery (level falling = water table rising).

    A recharge event is:
      - Rainfall >= MIN_RAINFALL_EVENT_MM on a day
      - Followed by water level decrease (recovery) within RECHARGE_WINDOW_HOURS
    """
    if rf.empty:
        log.warning("No rainfall data — cannot detect recharge events.")
        return []

    events = []
    rf["date"] = pd.to_datetime(rf["date"])

    # Only look at significant rainfall events
    rain_events = rf[rf["rainfall_mm"] >= MIN_RAINFALL_EVENT_MM].copy()

    for _, rain_row in rain_events.iterrows():
        rain_date  = pd.Timestamp(rain_row["date"])
        rain_mm    = float(rain_row["rainfall_mm"])

        # Get water level at time of rainfall
        pre_window = df[df["timestamp"] <= rain_date]
        if pre_window.empty:
            continue
        level_at_rain = float(pre_window["water_level_m"].iloc[-1])

        # Look for recovery in the next RECHARGE_WINDOW_HOURS
        post_window = df[
            (df["timestamp"] > rain_date) &
            (df["timestamp"] <= rain_date + timedelta(hours=RECHARGE_WINDOW_HOURS))
        ]
        if post_window.empty:
            continue

        min_level_after = float(post_window["water_level_m"].min())
        recovery_m      = level_at_rain - min_level_after   # positive = water rose

        if recovery_m > 0.01:   # at least 1cm recovery
            # Find when the recovery started (lag detection)
            recovery_row = post_window.loc[post_window["water_level_m"].idxmin()]
            lag_hours    = (
                pd.Timestamp(recovery_row["timestamp"]) - rain_date
            ).total_seconds() / 3600

            events.append({
                "date":          rain_date.strftime("%Y-%m-%d"),
                "rainfall_mm":   round(rain_mm, 1),
                "level_before_m": round(level_at_rain, 3),
                "level_after_m":  round(min_level_after, 3),
                "recovery_m":    round(recovery_m, 3),
                "lag_hours":     round(lag_hours, 1),
                "recharge_rate_m_per_day": round(
                    recovery_m / max(lag_hours / 24, 0.1), 4
                ),
            })

    events = sorted(events, key=lambda x: x["date"], reverse=True)
    log.info(f"Detected {len(events)} recharge events.")
    return events


# ═══════════════════════════════════════════════════════════════
# RECHARGE RATE
# ═══════════════════════════════════════════════════════════════

def _compute_recharge_rate(events: list[dict]) -> float:
    """
    Average recharge rate across all detected events (metres/day).
    Returns 0.0 if no events detected.
    """
    if not events:
        return 0.0
    rates = [e["recharge_rate_m_per_day"] for e in events if e["recharge_rate_m_per_day"] > 0]
    return round(float(np.mean(rates)), 4) if rates else 0.0


# ═══════════════════════════════════════════════════════════════
# LAG TIME
# ═══════════════════════════════════════════════════════════════

def _compute_lag_time(events: list[dict]) -> float:
    """
    Average lag time (hours) between rainfall event and water level response.
    Alluvial aquifers typically respond in 6–12h; Hard Rock in 24–48h.
    """
    if not events:
        return 0.0
    lags = [e["lag_hours"] for e in events if 0 < e["lag_hours"] <= MAX_LAG_HOURS]
    return round(float(np.mean(lags)), 1) if lags else 0.0


# ═══════════════════════════════════════════════════════════════
# NET RECHARGE (Pre vs Post Monsoon)
# ═══════════════════════════════════════════════════════════════

def _compute_net_recharge(df: pd.DataFrame) -> dict:
    """
    Net recharge = post-monsoon level minus pre-monsoon level.
    Negative result = water table deepened (net depletion this year).
    Positive result = water table recovered (net recharge this year).
    """
    df = df.copy()
    df["month"] = pd.to_datetime(df["timestamp"]).dt.month

    pre_monsoon  = df[df["month"].isin(PRE_MONSOON_MONTHS)]
    post_monsoon = df[df["month"].isin(POST_MONSOON_MONTHS)]

    pre_level  = float(pre_monsoon["water_level_m"].mean())  if not pre_monsoon.empty  else None
    post_level = float(post_monsoon["water_level_m"].mean()) if not post_monsoon.empty else None

    if pre_level is None or post_level is None:
        return {
            "net_recharge_m":      None,
            "pre_monsoon_level_m": pre_level,
            "post_monsoon_level_m": post_level,
        }

    # Positive net_recharge = level dropped (water table rose = good)
    net_recharge = round(pre_level - post_level, 3)

    return {
        "net_recharge_m":       net_recharge,
        "pre_monsoon_level_m":  round(pre_level,  3),
        "post_monsoon_level_m": round(post_level, 3),
    }


# ═══════════════════════════════════════════════════════════════
# RECHARGE CAPACITY
# ═══════════════════════════════════════════════════════════════

def _compute_recharge_capacity(
    df: pd.DataFrame,
    station_meta: dict,
) -> Optional[float]:
    """
    Remaining recharge capacity = well_depth_m - current_level_m.
    How many more metres can the water table rise before the well is full.
    """
    well_depth = station_meta.get("well_depth_m")
    if not well_depth or df.empty:
        return None
    current = float(df["water_level_m"].iloc[-1])
    return round(float(well_depth) - current, 3)


# ═══════════════════════════════════════════════════════════════
# ZONE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

def _classify_recharge_zone(
    net_recharge_m: Optional[float],
    recharge_rate:  float,
    aquifer_type:   str,
) -> str:
    """
    Classify recharge zone status:
      - good_recharge     : net positive, meaningful recharge rate
      - moderate_recharge : some recovery but below expected
      - stressed          : minimal recharge
      - critically_stressed : zero or negative recharge
    """
    if net_recharge_m is None:
        return "insufficient_data"

    # Adjust expectations by aquifer type
    # Alluvial recharges fast; Hard Rock recharges slowly
    expected_rate = 0.05 if "hard" in aquifer_type.lower() else 0.15

    if net_recharge_m > 0.5 and recharge_rate >= expected_rate:
        return "good_recharge"
    elif net_recharge_m > 0 and recharge_rate > 0:
        return "moderate_recharge"
    elif net_recharge_m <= 0 and recharge_rate == 0:
        return "critically_stressed"
    else:
        return "stressed"


# ═══════════════════════════════════════════════════════════════
# BATCH ANALYSIS
# ═══════════════════════════════════════════════════════════════

def estimate_recharge_all_stations(
    readings_df:   pd.DataFrame,
    rainfall_df:   pd.DataFrame,
    stations_df:   pd.DataFrame,
) -> list[dict]:
    """
    Run Task 2 recharge estimation for all stations.
    Returns list of result dicts, one per station.
    """
    log.info(f"Task 2 batch analysis — {len(stations_df)} stations")
    results = []
    for _, station in stations_df.iterrows():
        try:
            result = estimate_recharge(
                readings_df, rainfall_df, station.to_dict()
            )
            results.append(result)
        except Exception as e:
            log.error(f"Task2 failed for {station.get('station_id')}: {e}")
            results.append(_empty_result(station.get("station_id", "?"), str(e)))
    return results


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _build_summary(
    station_id:   str,
    recharge_rate: float,
    net_recharge:  dict,
    zone_status:   str,
    aquifer_type:  str,
) -> str:
    net = net_recharge.get("net_recharge_m")
    net_str = f"{net:+.3f}m" if net is not None else "N/A"
    return (
        f"Station {station_id} ({aquifer_type}): "
        f"recharge rate {recharge_rate}m/day, "
        f"net seasonal recharge {net_str}. "
        f"Zone: {zone_status.replace('_', ' ')}."
    )


def _empty_result(station_id: str, reason: str) -> dict:
    return {
        "station_id":              station_id,
        "aquifer_type":            "Unknown",
        "recharge_rate_m_per_day": 0.0,
        "lag_hours":               0.0,
        "net_recharge_m":          None,
        "pre_monsoon_level_m":     None,
        "post_monsoon_level_m":    None,
        "recharge_events":         [],
        "recharge_capacity_m":     None,
        "zone_status":             "insufficient_data",
        "summary":                 reason,
    }