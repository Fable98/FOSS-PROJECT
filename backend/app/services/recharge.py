"""
app/services/recharge.py — SubTerra
Service layer for Task 2 — Dynamic Recharge Estimation.
"""
import logging
from datetime import datetime, timedelta, timezone
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
    """Fetch readings + rainfall from DB and run Task 2 for one station."""
    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station:
        return {"error": f"Station {station_id} not found", "station_id": station_id}

    station_meta = {
        "station_id":   station.station_id,
        "state":        station.state,
        "district":     station.district,
        "aquifer_type": station.aquifer_type,
        "well_depth_m": station.well_depth_m,
    }

    # Fetch ALL readings (no time filter — we need full monsoon window)
    reading_rows = (
        db.query(DWLRReading)
        .filter(DWLRReading.station_id == station_id)
        .order_by(DWLRReading.timestamp)
        .limit(15000)
        .all()
    )

    if not reading_rows:
        return {"error": f"No readings for station {station_id}", "station_id": station_id}

    # Fetch rainfall — no strict filter since rainfall may be empty
    rainfall_rows = (
        db.query(Rainfall)
        .filter(
            Rainfall.state    == station.state,
            Rainfall.district == station.district,
        )
        .order_by(Rainfall.date)
        .all()
    )

    readings_df = _readings_to_df(reading_rows)
    rainfall_df = _rainfall_to_df(rainfall_rows)

    log.info(f"Task2 [{station_id}]: {len(readings_df)} readings, {len(rainfall_df)} rainfall rows")
    return estimate_recharge(readings_df, rainfall_df, station_meta)


def get_recharge_batch(
    db:       Session,
    state:    Optional[str] = None,
    district: Optional[str] = None,
    days:     int = 365,
) -> list[dict]:
    """Run Task 2 for all stations."""
    station_query = db.query(Station)
    if state:
        station_query = station_query.filter(Station.state.ilike(f"%{state}%"))
    if district:
        station_query = station_query.filter(Station.district.ilike(f"%{district}%"))

    stations = station_query.all()
    if not stations:
        return []

    station_ids = [s.station_id for s in stations]
    reading_rows  = db.query(DWLRReading).filter(DWLRReading.station_id.in_(station_ids)).limit(100000).all()
    rainfall_rows = db.query(Rainfall).all()

    readings_df = _readings_to_df(reading_rows)
    rainfall_df = _rainfall_to_df(rainfall_rows)
    stations_df = pd.DataFrame([{
        "station_id": s.station_id, "state": s.state,
        "district": s.district, "aquifer_type": s.aquifer_type, "well_depth_m": s.well_depth_m,
    } for s in stations])

    return estimate_recharge_all_stations(readings_df, rainfall_df, stations_df)


def _readings_to_df(rows) -> pd.DataFrame:
    df = pd.DataFrame([{
        "station_id":        r.station_id,
        "timestamp":         r.timestamp,
        "water_level_m":     r.water_level_m,
        "data_quality_flag": r.data_quality_flag or "G",
    } for r in rows])
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("Asia/Kolkata")
    return df


def _rainfall_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["state","district","date","rainfall_mm"])
    return pd.DataFrame([{
        "state": r.state, "district": r.district,
        "date": r.date, "rainfall_mm": r.rainfall_mm,
    } for r in rows])