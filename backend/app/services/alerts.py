"""
SubTerra — Alert Engine
backend/app/services/alerts.py

Generates alerts by crossing three data sources:
  1. Live DWLR readings     → water level threshold breaches
  2. Task 1 output          → rate-of-change alerts (analytics.py)
  3. Task 3 / evaluation.py → CGWB status alerts

Alert severity levels:
  CRITICAL  → immediate action needed
  WARNING   → watch closely
  INFO      → informational, no immediate risk

CGWB thresholds (mirrors evaluation.py — single source of truth):
  Safe           → < 8m
  Semi-Critical  → 8–15m
  Critical       → 15–25m
  Over-Exploited → > 25m

Key name contract with other modules:
  analytics.py  → "avg_daily_change_m", "analysed_at", "current_level_m", "trend"
  evaluation.py → "status", "current_level_m", "state"

Usage:
  from app.services.alerts import generate_alerts, get_active_alerts
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

log = logging.getLogger("subterra.alerts")

# ── CGWB Level Thresholds (metres) ────────────────────────────
# Mirrors evaluation.py — if you change these, change both.
THRESHOLD_SEMI_CRITICAL  =  8.0    # m — above this = Semi-Critical
THRESHOLD_CRITICAL       = 15.0    # m — above this = Critical
THRESHOLD_OVER_EXPLOITED = 25.0    # m — above this = Over-Exploited

# ── Rate of Change Thresholds ─────────────────────────────────
RATE_WARNING_M_PER_DAY   = 0.10    # m/day — watch
RATE_CRITICAL_M_PER_DAY  = 0.50    # m/day — urgent

# ── Sudden Drop Threshold ─────────────────────────────────────
SUDDEN_DROP_M_PER_HOUR   = 2.0     # m in 1 hour = possible over-extraction

# ── Lookback window for sudden drop check ─────────────────────
ALERT_LOOKBACK_HOURS     = 48      # scan last 48 hours of readings

# ── Alert severity constants ──────────────────────────────────
CRITICAL = "CRITICAL"
WARNING  = "WARNING"
INFO     = "INFO"

# ── CGWB status rank (for degradation check) ──────────────────
_STATUS_RANK = {
    "Safe":           0,
    "Semi-Critical":  1,
    "Critical":       2,
    "Over-Exploited": 3,
}


# ═══════════════════════════════════════════════════════════════
# ALERT BUILDER
# ═══════════════════════════════════════════════════════════════

def _alert(
    station_id:   str,
    alert_type:   str,
    severity:     str,
    message:      str,
    value:        Optional[float] = None,
    threshold:    Optional[float] = None,
    triggered_at: Optional[datetime] = None,
    state:        Optional[str] = None,
) -> dict:
    """Build a standardised alert dict."""
    return {
        "station_id":   station_id,
        "state":        state,                  # for state-level filtering in API
        "alert_type":   alert_type,
        "severity":     severity,
        "message":      message,
        "value":        round(value, 3) if value is not None else None,
        "threshold":    threshold,
        "triggered_at": (triggered_at or datetime.now(timezone.utc)).isoformat(),
        "acknowledged": False,
    }


# ═══════════════════════════════════════════════════════════════
# CHECK 1 — CGWB Level Threshold Breach
# ═══════════════════════════════════════════════════════════════

def check_level_thresholds(
    station_id:    str,
    current_level: float,
    as_of:         Optional[datetime] = None,
    state:         Optional[str] = None,
) -> list[dict]:
    """
    Alert if current water level crosses CGWB classification bands.
    Only the most severe band fires — elif chain ensures one alert max.
    """
    alerts = []

    if current_level >= THRESHOLD_OVER_EXPLOITED:
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "level_over_exploited",
            severity     = CRITICAL,
            message      = (
                f"Water level {current_level:.2f}m exceeds Over-Exploited "
                f"threshold ({THRESHOLD_OVER_EXPLOITED}m). Immediate intervention required."
            ),
            value        = current_level,
            threshold    = THRESHOLD_OVER_EXPLOITED,
            triggered_at = as_of,
            state        = state,
        ))

    elif current_level >= THRESHOLD_CRITICAL:
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "level_critical",
            severity     = CRITICAL,
            message      = (
                f"Water level {current_level:.2f}m in Critical band "
                f"({THRESHOLD_CRITICAL}–{THRESHOLD_OVER_EXPLOITED}m)."
            ),
            value        = current_level,
            threshold    = THRESHOLD_CRITICAL,
            triggered_at = as_of,
            state        = state,
        ))

    elif current_level >= THRESHOLD_SEMI_CRITICAL:
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "level_semi_critical",
            severity     = WARNING,
            message      = (
                f"Water level {current_level:.2f}m in Semi-Critical band "
                f"({THRESHOLD_SEMI_CRITICAL}–{THRESHOLD_CRITICAL}m)."
            ),
            value        = current_level,
            threshold    = THRESHOLD_SEMI_CRITICAL,
            triggered_at = as_of,
            state        = state,
        ))

    return alerts


# ═══════════════════════════════════════════════════════════════
# CHECK 2 — Rate of Change Alert
# ═══════════════════════════════════════════════════════════════

def check_rate_of_change(
    station_id:   str,
    rate_per_day: float,
    as_of:        Optional[datetime] = None,
    state:        Optional[str] = None,
) -> list[dict]:
    """
    Alert if water table is deepening too fast.
    rate_per_day comes from analytics.py "avg_daily_change_m".
    Positive = deepening (worsening). Negative = recovering — no alert.
    """
    alerts = []

    if rate_per_day >= RATE_CRITICAL_M_PER_DAY:
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "rate_critical",
            severity     = CRITICAL,
            message      = (
                f"Water table deepening at {rate_per_day:.3f}m/day — "
                f"exceeds critical rate ({RATE_CRITICAL_M_PER_DAY}m/day). "
                f"Likely heavy extraction."
            ),
            value        = rate_per_day,
            threshold    = RATE_CRITICAL_M_PER_DAY,
            triggered_at = as_of,
            state        = state,
        ))

    elif rate_per_day >= RATE_WARNING_M_PER_DAY:
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "rate_warning",
            severity     = WARNING,
            message      = (
                f"Water table deepening at {rate_per_day:.3f}m/day — "
                f"above warning threshold ({RATE_WARNING_M_PER_DAY}m/day)."
            ),
            value        = rate_per_day,
            threshold    = RATE_WARNING_M_PER_DAY,
            triggered_at = as_of,
            state        = state,
        ))

    return alerts


# ═══════════════════════════════════════════════════════════════
# CHECK 3 — Sudden Drop (Over-Extraction Event)
# ═══════════════════════════════════════════════════════════════

def check_sudden_drop(
    station_id:  str,
    readings_df: pd.DataFrame,
    state:       Optional[str] = None,
) -> list[dict]:
    """
    Scan recent readings for water table deepening > SUDDEN_DROP_M_PER_HOUR
    within any single hour. Signals a possible large-scale extraction event.
    All timestamps normalised to UTC to avoid IST/UTC mismatch crashes.
    """
    alerts = []

    df = readings_df[readings_df["station_id"] == station_id].copy()
    if df.empty or len(df) < 2:
        return alerts

    # Normalise to UTC — handles both naive and tz-aware timestamps safely
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=ALERT_LOOKBACK_HOURS)
    df = df[df["timestamp"] >= cutoff]

    if df.empty:
        return alerts

    hourly = (
        df.set_index("timestamp")
        .resample("h")["water_level_m"]
        .mean()
        .reset_index()
    )
    hourly["change"] = hourly["water_level_m"].diff()

    events = hourly[hourly["change"] > SUDDEN_DROP_M_PER_HOUR]

    for _, row in events.iterrows():
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "sudden_drop",
            severity     = CRITICAL,
            message      = (
                f"Water table deepened {row['change']:.2f}m in 1 hour — "
                f"possible large-scale extraction event."
            ),
            value        = float(row["change"]),
            threshold    = SUDDEN_DROP_M_PER_HOUR,
            triggered_at = row["timestamp"].to_pydatetime(),
            state        = state,
        ))

    return alerts


# ═══════════════════════════════════════════════════════════════
# CHECK 4 — No Data Alert
# ═══════════════════════════════════════════════════════════════

def check_no_data(
    station_id:    str,
    last_reading:  Optional[datetime],
    max_gap_hours: int = 2,
    state:         Optional[str] = None,
) -> list[dict]:
    """
    Alert if a station has gone silent for > max_gap_hours.
    DWLR sensors report every 15 min — a 2-hour gap = sensor or comms fault.

    Accepts both datetime and pandas Timestamp for last_reading.
    """
    alerts = []
    now = datetime.now(timezone.utc)

    if last_reading is None:
        alerts.append(_alert(
            station_id = station_id,
            alert_type = "no_data",
            severity   = WARNING,
            message    = f"Station {station_id} has never reported data.",
            state      = state,
        ))
        return alerts

    # Convert pandas Timestamp → datetime if needed
    if hasattr(last_reading, "to_pydatetime"):
        last_reading = last_reading.to_pydatetime()

    # Make timezone-aware if naive
    if last_reading.tzinfo is None:
        last_reading = last_reading.replace(tzinfo=timezone.utc)

    gap_hours = (now - last_reading).total_seconds() / 3600

    if gap_hours > max_gap_hours:
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "no_data",
            severity     = WARNING,
            message      = (
                f"No readings from station {station_id} for "
                f"{gap_hours:.1f} hours. Possible sensor or comms fault."
            ),
            value        = round(gap_hours, 1),
            threshold    = float(max_gap_hours),
            triggered_at = now,
            state        = state,
        ))

    return alerts


# ═══════════════════════════════════════════════════════════════
# CHECK 5 — CGWB Status Degradation
# ═══════════════════════════════════════════════════════════════

def check_status_degradation(
    station_id:      str,
    current_status:  str,
    previous_status: str,
    current_level:   float,
    as_of:           Optional[datetime] = None,
    state:           Optional[str] = None,
) -> list[dict]:
    """
    Alert when CGWB classification worsens vs previous check.
    e.g. Safe → Semi-Critical, or Semi-Critical → Critical.
    """
    alerts = []

    prev_rank = _STATUS_RANK.get(previous_status, 0)
    curr_rank = _STATUS_RANK.get(current_status, 0)

    if curr_rank > prev_rank:
        severity = CRITICAL if curr_rank >= 2 else WARNING
        alerts.append(_alert(
            station_id   = station_id,
            alert_type   = "status_degradation",
            severity     = severity,
            message      = (
                f"Station {station_id} degraded from {previous_status} → "
                f"{current_status} (level: {current_level:.2f}m)."
            ),
            value        = current_level,
            triggered_at = as_of,
            state        = state,
        ))

    return alerts


# ═══════════════════════════════════════════════════════════════
# MAIN — Generate all alerts for a single station
# ═══════════════════════════════════════════════════════════════

def generate_alerts(
    station_id:      str,
    readings_df:     pd.DataFrame,
    task1_result:    Optional[dict] = None,
    task3_result:    Optional[dict] = None,
    previous_status: Optional[str]  = None,
    last_reading_at: Optional[datetime] = None,
    state:           Optional[str] = None,
) -> list[dict]:
    """
    Run all 5 alert checks for a single station and return a combined list.

    Key name contract:
      task1_result (analytics.py):
        "avg_daily_change_m"  → rate of deepening per day
        "analysed_at"         → ISO timestamp of analysis
        "current_level_m"     → current water level in metres
        "trend"               → "Declining" | "Recovering" | "Stable"

      task3_result (evaluation.py):
        "status"              → CGWB classification label
        "current_level_m"     → current water level in metres
        "state"               → state name

    Returns:
        List of alert dicts sorted by severity (CRITICAL first).
    """
    all_alerts = []

    # ── Extract values from task results ─────────────────────
    current_level = None
    rate_per_day  = None
    as_of         = None
    cgwb_status   = None

    if task1_result:
        current_level   = task1_result.get("current_level_m")
        rate_per_day    = task1_result.get("avg_daily_change_m")   # ← correct key
        as_of_str       = task1_result.get("analysed_at")           # ← correct key
        as_of           = datetime.fromisoformat(as_of_str) if as_of_str else None
        state           = state or None   # task1 doesn't carry state

    if task3_result:
        current_level = current_level or task3_result.get("current_level_m")
        cgwb_status   = task3_result.get("status")          # ← correct key
        state         = state or task3_result.get("state")  # ← pull state from task3

    # ── Check 1: Level thresholds ────────────────────────────
    if current_level is not None:
        all_alerts += check_level_thresholds(
            station_id, current_level, as_of, state
        )

    # ── Check 2: Rate of change (only when deepening) ────────
    # avg_daily_change_m is positive when deepening, negative when recovering
    if rate_per_day is not None and rate_per_day > 0:
        all_alerts += check_rate_of_change(
            station_id, rate_per_day, as_of, state
        )

    # ── Check 3: Sudden drop ─────────────────────────────────
    all_alerts += check_sudden_drop(station_id, readings_df, state)

    # ── Check 4: No data ─────────────────────────────────────
    all_alerts += check_no_data(station_id, last_reading_at, state=state)

    # ── Check 5: Status degradation ─────────────────────────
    if cgwb_status and previous_status and current_level is not None:
        all_alerts += check_status_degradation(
            station_id, cgwb_status, previous_status,
            current_level, as_of, state,
        )

    # ── Sort: CRITICAL first, then WARNING, then INFO ────────
    _order = {CRITICAL: 0, WARNING: 1, INFO: 2}
    all_alerts.sort(key=lambda a: _order.get(a["severity"], 9))

    log.info(
        f"Alerts [{station_id}] — "
        f"{sum(1 for a in all_alerts if a['severity'] == CRITICAL)} critical, "
        f"{sum(1 for a in all_alerts if a['severity'] == WARNING)} warnings"
    )

    return all_alerts


# ═══════════════════════════════════════════════════════════════
# BATCH — Run alerts for all stations in readings_df
# ═══════════════════════════════════════════════════════════════

def generate_all_alerts(
    readings_df:       pd.DataFrame,
    task1_results:     Optional[list[dict]] = None,
    task3_results:     Optional[list[dict]] = None,
    previous_statuses: Optional[dict] = None,
) -> dict:
    """
    Run generate_alerts() for every station in readings_df.

    Args:
        readings_df       : all DWLR readings (must have station_id, timestamp,
                            water_level_m, and optionally state)
        task1_results     : list of analytics.py result dicts (one per station)
        task3_results     : list of evaluation.py result dicts (one per station)
        previous_statuses : {station_id: last_cgwb_status_string}

    Returns:
        {
            "generated_at":   ISO timestamp,
            "total_alerts":   int,
            "critical_count": int,
            "warning_count":  int,
            "by_station":     {station_id: [alert, ...]},
            "all_alerts":     [alert, ...] sorted by severity
        }
    """
    station_ids = readings_df["station_id"].unique().tolist()
    log.info(f"Generating alerts for {len(station_ids)} stations …")

    # Index by station_id for O(1) lookup
    t1_idx    = {r["station_id"]: r for r in (task1_results or [])}
    t3_idx    = {r["station_id"]: r for r in (task3_results or [])}
    prev_s    = previous_statuses or {}

    # State per station from readings_df (if present)
    state_by_station: dict = {}
    if "state" in readings_df.columns:
        state_by_station = (
            readings_df.groupby("station_id")["state"]
            .first()
            .to_dict()
        )

    # Latest timestamp per station — convert to pydatetime for check_no_data
    latest_times: dict = (
        readings_df.groupby("station_id")["timestamp"]
        .max()
        .to_dict()
    )

    by_station: dict = {}
    all_alerts: list = []

    for sid in station_ids:
        try:
            alerts = generate_alerts(
                station_id      = sid,
                readings_df     = readings_df,
                task1_result    = t1_idx.get(sid),
                task3_result    = t3_idx.get(sid),
                previous_status = prev_s.get(sid),
                last_reading_at = latest_times.get(sid),
                state           = state_by_station.get(sid),
            )
            by_station[sid] = alerts
            all_alerts.extend(alerts)
        except Exception as e:
            log.error(f"Alert generation failed for {sid}: {e}")

    # Re-sort combined list
    _order = {CRITICAL: 0, WARNING: 1, INFO: 2}
    all_alerts.sort(key=lambda a: _order.get(a["severity"], 9))

    return {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "total_alerts":   len(all_alerts),
        "critical_count": sum(1 for a in all_alerts if a["severity"] == CRITICAL),
        "warning_count":  sum(1 for a in all_alerts if a["severity"] == WARNING),
        "by_station":     by_station,
        "all_alerts":     all_alerts,
    }


# ═══════════════════════════════════════════════════════════════
# FILTER HELPERS — used by API routes
# ═══════════════════════════════════════════════════════════════

def get_active_alerts(
    all_alerts: list[dict],
    severity:   Optional[str] = None,
    state:      Optional[str] = None,
    station_id: Optional[str] = None,
    limit:      int = 100,
) -> list[dict]:
    """
    Filter alert list by severity, state, or station.
    Used by GET /api/alerts route.
    All filters are optional and combinable.
    """
    results = all_alerts

    if severity:
        results = [a for a in results if a["severity"] == severity.upper()]
    if state:
        results = [a for a in results if a.get("state") == state]
    if station_id:
        results = [a for a in results if a["station_id"] == station_id]

    return results[:limit]


def summarise_alerts(all_alerts: list[dict]) -> dict:
    """
    Return a concise summary for the dashboard header.
    """
    return {
        "total":    len(all_alerts),
        "critical": sum(1 for a in all_alerts if a["severity"] == CRITICAL),
        "warning":  sum(1 for a in all_alerts if a["severity"] == WARNING),
        "types":    list({a["alert_type"] for a in all_alerts}),
    }