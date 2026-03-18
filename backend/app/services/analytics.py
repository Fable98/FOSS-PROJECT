"""
app/services/analytics.py — SubTerra
Service layer for Task 1 — Water Level Fluctuation Analysis.
Fetches data from DB, calls Task 1 algorithm, returns results.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.station import DWLRReading, Station
from algorithms.task1_fluctuation import analyze_fluctuations, analyze_all_stations

log = logging.getLogger("subterra.service.analytics")


def get_fluctuation_analysis(
    station_id: str,
    db:         Session,
    hours:      int = 168,   # default 7 days
) -> dict:
    """
    Fetch readings from DB and run Task 1 analysis for one station.
    Called by: GET /api/task1/{station_id}

    Args:
        station_id : DWLR station ID
        db         : SQLAlchemy session
        hours      : How many hours of history to analyse (default 7 days)

    Returns Task 1 result dict.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    rows = (
        db.query(DWLRReading)
        .filter(
            DWLRReading.station_id == station_id,
            DWLRReading.timestamp  >= since,
        )
        .order_by(DWLRReading.timestamp)
        .all()
    )

    if not rows:
        log.warning(f"No readings in DB for station {station_id} in last {hours}h")
        return {"error": f"No data found for station {station_id}", "station_id": station_id}

    df = _readings_to_df(rows)
    return analyze_fluctuations(df, station_id)


def get_fluctuation_analysis_batch(
    db:       Session,
    state:    Optional[str] = None,
    district: Optional[str] = None,
    hours:    int = 48,
) -> list[dict]:
    """
    Run Task 1 for all stations (optionally filtered by state/district).
    Called by: GET /api/task1 (bulk endpoint)
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # Build station filter
    station_query = db.query(Station)
    if state:
        station_query = station_query.filter(Station.state.ilike(f"%{state}%"))
    if district:
        station_query = station_query.filter(Station.district.ilike(f"%{district}%"))

    station_ids = [s.station_id for s in station_query.all()]

    if not station_ids:
        return []

    rows = (
        db.query(DWLRReading)
        .filter(
            DWLRReading.station_id.in_(station_ids),
            DWLRReading.timestamp  >= since,
        )
        .order_by(DWLRReading.timestamp)
        .all()
    )

    if not rows:
        return []

    df = _readings_to_df(rows)
    return analyze_all_stations(df)


def get_anomalies(
    db:       Session,
    state:    Optional[str] = None,
    hours:    int = 24,
) -> list[dict]:
    """
    Return all anomalous readings in the last N hours.
    Called by: GET /api/alerts
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    query = (
        db.query(DWLRReading, Station)
        .join(Station, DWLRReading.station_id == Station.station_id)
        .filter(
            DWLRReading.is_anomaly == True,
            DWLRReading.timestamp  >= since,
        )
    )
    if state:
        query = query.filter(Station.state.ilike(f"%{state}%"))

    results = []
    for reading, station in query.order_by(DWLRReading.timestamp.desc()).limit(100).all():
        results.append({
            "station_id":    reading.station_id,
            "station_name":  station.station_name,
            "state":         station.state,
            "district":      station.district,
            "timestamp":     reading.timestamp.isoformat(),
            "water_level_m": reading.water_level_m,
            "anomaly_reason": reading.anomaly_reason,
        })

    return results


# ── Internal helper ────────────────────────────────────────────────────────────

def _readings_to_df(rows) -> pd.DataFrame:
    return pd.DataFrame([{
        "station_id":        r.station_id,
        "timestamp":         r.timestamp,
        "water_level_m":     r.water_level_m,
        "data_quality_flag": r.data_quality_flag,
        "is_anomaly":        r.is_anomaly,
        "anomaly_reason":    r.anomaly_reason,
    } for r in rows])
