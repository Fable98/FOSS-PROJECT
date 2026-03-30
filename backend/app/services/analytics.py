"""
app/services/analytics.py — SubTerra
Service layer for Task 1 — Water Level Fluctuation Analysis.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.station import DWLRReading, Station
from algorithms.task1_fluctuation import analyze_fluctuations, analyze_all_stations

log = logging.getLogger("subterra.service.analytics")


def get_fluctuation_analysis(
    station_id: str,
    db:         Session,
    hours:      int = 720,   # extended to 30 days default
) -> dict:
    """Fetch readings from DB and run Task 1 analysis for one station."""

    # Use timezone-aware UTC now — avoids naive vs aware comparison issues
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows = (
        db.query(DWLRReading)
        .filter(
            DWLRReading.station_id == station_id,
            DWLRReading.timestamp  >= since,
        )
        .order_by(DWLRReading.timestamp)
        .all()
    )

    # If no rows with timezone filter, try without (handles tz-naive stored data)
    if not rows:
        since_naive = datetime.utcnow() - timedelta(hours=hours)
        rows = (
            db.query(DWLRReading)
            .filter(DWLRReading.station_id == station_id)
            .order_by(DWLRReading.timestamp)
            .limit(5000)
            .all()
        )

    if not rows:
        log.warning(f"No readings in DB for station {station_id}")
        return {"error": f"No data found for station {station_id}", "station_id": station_id}

    df = _readings_to_df(rows)
    log.info(f"Task1 [{station_id}]: {len(df)} readings loaded")
    return analyze_fluctuations(df, station_id)


def get_fluctuation_analysis_batch(
    db:       Session,
    state:    Optional[str] = None,
    district: Optional[str] = None,
    hours:    int = 720,
) -> list[dict]:
    """Run Task 1 for all stations."""
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
        .filter(DWLRReading.station_id.in_(station_ids))
        .order_by(DWLRReading.timestamp)
        .limit(50000)
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
    """Return all anomalous readings in the last N hours."""
    query = (
        db.query(DWLRReading, Station)
        .join(Station, DWLRReading.station_id == Station.station_id)
        .filter(DWLRReading.is_anomaly == True)
    )
    if state:
        query = query.filter(Station.state.ilike(f"%{state}%"))

    results = []
    for reading, station in query.order_by(DWLRReading.timestamp.desc()).limit(100).all():
        results.append({
            "station_id":     reading.station_id,
            "station_name":   station.station_name,
            "state":          station.state,
            "district":       station.district,
            "timestamp":      reading.timestamp.isoformat() if reading.timestamp else None,
            "water_level_m":  reading.water_level_m,
            "anomaly_reason": reading.anomaly_reason,
        })
    return results


def _readings_to_df(rows) -> pd.DataFrame:
    df = pd.DataFrame([{
        "station_id":        r.station_id,
        "timestamp":         r.timestamp,
        "water_level_m":     r.water_level_m,
        "data_quality_flag": r.data_quality_flag or "G",
        "is_anomaly":        r.is_anomaly or False,
        "anomaly_reason":    r.anomaly_reason or "",
    } for r in rows])

    if df.empty:
        return df

    # Safely handle timezone — works whether timestamps are naive or aware
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df