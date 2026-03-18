"""
app/services/alerts.py — SubTerra
Service layer for Task 3 — Resource Evaluation + Alert Engine.
Evaluates groundwater status and generates alerts for critical zones.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.station import DWLRReading, Station
from algorithms.task3_evaluation import (
    evaluate_station,
    evaluate_all_stations,
    generate_district_scorecard,
    generate_state_scorecard,
)

log = logging.getLogger("subterra.service.alerts")

# Statuses that trigger an alert
ALERT_STATUSES = {"critical", "over_exploited"}


def get_station_evaluation(
    station_id:   str,
    db:           Session,
    days:         int = 365,
    stage_of_dev: Optional[float] = None,
) -> dict:
    """
    Fetch readings and run Task 3 evaluation for one station.
    Called by: GET /api/task3/{station_id}
    """
    since = datetime.utcnow() - timedelta(days=days)

    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station:
        return {"error": f"Station {station_id} not found"}

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
        return {"error": f"No readings for station {station_id}"}

    readings_df  = _readings_to_df(rows)
    station_meta = _station_to_dict(station)

    return evaluate_station(readings_df, station_meta, stage_of_dev)


def get_active_alerts(
    db:       Session,
    state:    Optional[str] = None,
    district: Optional[str] = None,
    days:     int = 2,
) -> list[dict]:
    """
    Return all stations currently in Critical or Over-Exploited status.
    Called by: GET /api/alerts
    """
    since = datetime.utcnow() - timedelta(days=days)

    station_query = db.query(Station)
    if state:
        station_query = station_query.filter(Station.state.ilike(f"%{state}%"))
    if district:
        station_query = station_query.filter(Station.district.ilike(f"%{district}%"))

    stations  = station_query.all()
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

    if not reading_rows:
        return []

    readings_df = _readings_to_df(reading_rows)
    stations_df = pd.DataFrame([_station_to_dict(s) for s in stations])

    results  = evaluate_all_stations(readings_df, stations_df)
    alerts   = [r for r in results if r.get("status") in ALERT_STATUSES]

    # Sort: over_exploited first, then critical; within each by level depth
    alerts.sort(key=lambda x: (
        -{"over_exploited": 2, "critical": 1}.get(x.get("status", ""), 0),
        -(x.get("current_level_m") or 0),
    ))

    log.info(f"Active alerts: {len(alerts)} stations in critical/over-exploited status.")
    return alerts


def get_district_scorecard(
    state:    str,
    district: str,
    db:       Session,
    days:     int = 365,
) -> dict:
    """
    Generate district-level groundwater health scorecard.
    Called by: GET /api/summary/{state}/{district}
    """
    since = datetime.utcnow() - timedelta(days=days)

    stations = (
        db.query(Station)
        .filter(
            Station.state.ilike(f"%{state}%"),
            Station.district.ilike(f"%{district}%"),
        )
        .all()
    )

    if not stations:
        return {"error": f"No stations found in {district}, {state}"}

    station_ids  = [s.station_id for s in stations]
    reading_rows = (
        db.query(DWLRReading)
        .filter(
            DWLRReading.station_id.in_(station_ids),
            DWLRReading.timestamp  >= since,
        )
        .all()
    )

    readings_df = _readings_to_df(reading_rows)
    stations_df = pd.DataFrame([_station_to_dict(s) for s in stations])

    station_results = evaluate_all_stations(readings_df, stations_df)
    scorecard       = generate_district_scorecard(station_results)

    scorecard["state"]    = state
    scorecard["district"] = district
    return scorecard


def get_state_scorecard(
    state: str,
    db:    Session,
    days:  int = 365,
) -> dict:
    """
    Generate state-level groundwater health scorecard.
    Called by: GET /api/summary/{state}
    """
    # Get all distinct districts in the state
    districts = (
        db.query(Station.district)
        .filter(Station.state.ilike(f"%{state}%"))
        .distinct()
        .all()
    )

    district_scorecards = {}
    for (district,) in districts:
        if district:
            card = get_district_scorecard(state, district, db, days)
            if "error" not in card:
                district_scorecards[district] = card

    if not district_scorecards:
        return {"error": f"No data for state: {state}"}

    scorecard       = generate_state_scorecard(district_scorecards)
    scorecard["state"] = state
    return scorecard


# ── Internal helpers ───────────────────────────────────────────────────────────

def _readings_to_df(rows) -> pd.DataFrame:
    return pd.DataFrame([{
        "station_id":    r.station_id,
        "timestamp":     r.timestamp,
        "water_level_m": r.water_level_m,
        "data_quality_flag": r.data_quality_flag,
    } for r in rows])


def _station_to_dict(s) -> dict:
    return {
        "station_id":   s.station_id,
        "station_name": s.station_name,
        "state":        s.state,
        "district":     s.district,
        "block":        s.block,
        "aquifer_type": s.aquifer_type,
        "well_depth_m": s.well_depth_m,
        "latitude":     s.latitude,
        "longitude":    s.longitude,
    }