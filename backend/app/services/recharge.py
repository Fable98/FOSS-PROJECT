"""
app/services/recharge.py — SubTerra
Service layer for Task 2 — Dynamic Recharge Estimation.
Fetches readings + rainfall from DB, calls Task 2 algorithm.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.station import DWLRReading, Rainfall, Station
from algorithms.task2_recharge import estimate_recharge, estimate_recharge_all_stations

log = logging.getLogger("subterra.service.recharge")


def get_recharge_estimate(
    station_id: str,
    db:         Session,
    days:       int = 365,
) -> dict:
    """
    Fetch readings + rainfall from DB and run Task 2 for one station.
    Called by: GET /api/task2/{station_id}

    Args:
        station_id : DWLR station ID
        db         : SQLAlchemy session
        days       : History window in days (default 1 year for monsoon comparison)

    Returns Task 2 result dict.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Fetch station metadata
    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station:
        return {"error": f"Station {station_id} not found", "station_id": station_id}

    station_meta = {
        "station_id":  station.station_id,
        "state":       station.state,
        "district":    station.district,
        "aquifer_type": station.aquifer_type,
        "well_depth_m": station.well_depth_m,
    }

    # Fetch readings
    reading_rows = (
        db.query(DWLRReading)
        .filter(
            DWLRReading.station_id == station_id,
            DWLRReading.timestamp  >= since,
        )
        .order_by(DWLRReading.timestamp)
        .all()
    )

    if not reading_rows:
        return {"error": f"No readings for station {station_id}", "station_id": station_id}

    # Fetch rainfall for station's district
    rainfall_rows = (
        db.query(Rainfall)
        .filter(
            Rainfall.state    == station.state,
            Rainfall.district == station.district,
            Rainfall.date     >= since.date(),
        )
        .order_by(Rainfall.date)
        .all()
    )

    readings_df = _readings_to_df(reading_rows)
    rainfall_df = _rainfall_to_df(rainfall_rows)

    return estimate_recharge(readings_df, rainfall_df, station_meta)


def get_recharge_batch(
    db:       Session,
    state:    Optional[str] = None,
    district: Optional[str] = None,
    days:     int = 365,
) -> list[dict]:
    """
    Run Task 2 for all stations (optionally filtered).
    Called by bulk recharge endpoint.
    """
    since = datetime.utcnow() - timedelta(days=days)

    station_query = db.query(Station)
    if state:
        station_query = station_query.filter(Station.state.ilike(f"%{state}%"))
    if district:
        station_query = station_query.filter(Station.district.ilike(f"%{district}%"))

    stations = station_query.all()
    if not stations:
        return []

    station_ids = [s.station_id for s in stations]

    reading_rows = (
        db.query(DWLRReading)
        .filter(
            DWLRReading.station_id.in_(station_ids),
            DWLRReading.timestamp  >= since,
        )
        .all()
    )

    states = list({s.state for s in stations if s.state})
    rainfall_rows = (
        db.query(Rainfall)
        .filter(
            Rainfall.state.in_(states),
            Rainfall.date >= since.date(),
        )
        .all()
    )

    readings_df = _readings_to_df(reading_rows)
    rainfall_df = _rainfall_to_df(rainfall_rows)
    stations_df = pd.DataFrame([{
        "station_id":   s.station_id,
        "state":        s.state,
        "district":     s.district,
        "aquifer_type": s.aquifer_type,
        "well_depth_m": s.well_depth_m,
    } for s in stations])

    return estimate_recharge_all_stations(readings_df, rainfall_df, stations_df)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _readings_to_df(rows) -> pd.DataFrame:
    return pd.DataFrame([{
        "station_id":    r.station_id,
        "timestamp":     r.timestamp,
        "water_level_m": r.water_level_m,
        "data_quality_flag": r.data_quality_flag,
    } for r in rows])


def _rainfall_to_df(rows) -> pd.DataFrame:
    return pd.DataFrame([{
        "state":       r.state,
        "district":    r.district,
        "date":        r.date,
        "rainfall_mm": r.rainfall_mm,
    } for r in rows])