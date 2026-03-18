"""
api/main.py — SubTerra
All FastAPI route definitions.
Wires URL endpoints to service layer functions.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from app.models.station import Station
from app.services.analytics import (
    get_fluctuation_analysis,
    get_fluctuation_analysis_batch,
    get_anomalies,
)
from app.services.recharge import get_recharge_estimate, get_recharge_batch
from app.services.alerts import (
    get_station_evaluation,
    get_active_alerts,
    get_district_scorecard,
    get_state_scorecard,
)

log    = logging.getLogger("subterra.api")
router = APIRouter()


@router.get("/health", tags=["System"])
def health_check():
    from db.database import check_connection
    return {"status": "ok", "db": check_connection(), "service": "SubTerra API v1"}


@router.get("/stations", tags=["Stations"])
def list_stations(
    state:    Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Station)
    if state:     query = query.filter(Station.state.ilike(f"%{state}%"))
    if district:  query = query.filter(Station.district.ilike(f"%{district}%"))
    stations = query.all()
    if not stations: raise HTTPException(status_code=404, detail="No stations found")
    return stations


@router.get("/stations/{station_id}", tags=["Stations"])
def get_station(station_id: str, db: Session = Depends(get_db)):
    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station: raise HTTPException(status_code=404, detail=f"Station {station_id} not found")
    return station


@router.get("/task1/{station_id}", tags=["Task 1 — Fluctuation"])
def task1_station(
    station_id: str,
    hours: int = Query(168, description="Hours of history (default 7 days)"),
    db: Session = Depends(get_db),
):
    result = get_fluctuation_analysis(station_id, db, hours=hours)
    if "error" in result: raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/task1", tags=["Task 1 — Fluctuation"])
def task1_bulk(
    state: Optional[str] = Query(None), district: Optional[str] = Query(None),
    hours: int = Query(48), db: Session = Depends(get_db),
):
    results = get_fluctuation_analysis_batch(db, state=state, district=district, hours=hours)
    if not results: raise HTTPException(status_code=404, detail="No data found")
    return results


@router.get("/task2/{station_id}", tags=["Task 2 — Recharge"])
def task2_station(
    station_id: str, days: int = Query(365), db: Session = Depends(get_db),
):
    result = get_recharge_estimate(station_id, db, days=days)
    if "error" in result: raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/task2", tags=["Task 2 — Recharge"])
def task2_bulk(
    state: Optional[str] = Query(None), district: Optional[str] = Query(None),
    days: int = Query(365), db: Session = Depends(get_db),
):
    results = get_recharge_batch(db, state=state, district=district, days=days)
    if not results: raise HTTPException(status_code=404, detail="No data found")
    return results


@router.get("/task3/{station_id}", tags=["Task 3 — Evaluation"])
def task3_station(
    station_id: str, days: int = Query(365),
    stage_of_dev: Optional[float] = Query(None), db: Session = Depends(get_db),
):
    result = get_station_evaluation(station_id, db, days=days, stage_of_dev=stage_of_dev)
    if "error" in result: raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/alerts", tags=["Alerts"])
def active_alerts(
    state: Optional[str] = Query(None), district: Optional[str] = Query(None),
    hours: int = Query(48), db: Session = Depends(get_db),
):
    alerts = get_active_alerts(db, state=state, district=district, days=hours // 24 or 2)
    return {"total": len(alerts), "alerts": alerts}


@router.get("/alerts/anomalies", tags=["Alerts"])
def anomaly_alerts(
    state: Optional[str] = Query(None), hours: int = Query(24), db: Session = Depends(get_db),
):
    anomalies = get_anomalies(db, state=state, hours=hours)
    return {"total": len(anomalies), "anomalies": anomalies}


@router.get("/summary/{state}", tags=["Scorecards"])
def state_summary(state: str, db: Session = Depends(get_db)):
    result = get_state_scorecard(state, db)
    if "error" in result: raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/summary/{state}/{district}", tags=["Scorecards"])
def district_summary(state: str, district: str, db: Session = Depends(get_db)):
    result = get_district_scorecard(state, district, db)
    if "error" in result: raise HTTPException(status_code=404, detail=result["error"])
    return result