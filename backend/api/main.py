"""
api/main.py — SubTerra — Phase 4 Final v2
"""
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db, SessionLocal
from app.models.station import DWLRReading, Station, Rainfall
from app.services.analytics import get_fluctuation_analysis, get_fluctuation_analysis_batch, get_anomalies
from app.services.recharge  import get_recharge_estimate, get_recharge_batch
from app.services.alerts    import (
    get_station_evaluation, get_active_alerts,
    get_district_scorecard, get_state_scorecard,
)

log    = logging.getLogger("subterra.api")
router = APIRouter()


@router.get("/health", tags=["System"])
def health_check():
    from db.database import check_connection
    db_ok = check_connection()
    station_count = 0
    reading_count = 0
    rainfall_count = 0

    if db_ok:
        try:
            with SessionLocal() as db:
                station_count = db.query(func.count(Station.station_id)).scalar() or 0
                reading_count = db.query(func.count()).select_from(DWLRReading).scalar() or 0
                rainfall_count = db.query(func.count()).select_from(Rainfall).scalar() or 0
        except Exception:
            station_count = 0
            reading_count = 0
            rainfall_count = 0

    data_mode = "live_like"
    if station_count and station_count < 500:
        data_mode = "demo_fallback"
    elif station_count == 0:
        data_mode = "empty"

    return {
        "status": "ok",
        "db": db_ok,
        "service": "SubTerra API v1",
        "station_count": station_count,
        "reading_count": reading_count,
        "rainfall_count": rainfall_count,
        "data_mode": data_mode,
    }


@router.get("/stations", tags=["Stations"])
def list_stations(state: Optional[str]=Query(None), district: Optional[str]=Query(None), db: Session=Depends(get_db)):
    query = db.query(Station)
    if state:    query = query.filter(Station.state.ilike(f"%{state}%"))
    if district: query = query.filter(Station.district.ilike(f"%{district}%"))
    stations = query.all()
    if not stations: raise HTTPException(404, "No stations found")
    return stations


@router.get("/stations/{station_id}", tags=["Stations"])
def get_station(station_id: str, db: Session=Depends(get_db)):
    s = db.query(Station).filter(Station.station_id == station_id).first()
    if not s: raise HTTPException(404, f"Station {station_id} not found")
    return s


@router.get("/task1/{station_id}", tags=["Task 1 — Fluctuation"])
def task1_station(station_id: str, hours: int=Query(720), db: Session=Depends(get_db)):
    result = get_fluctuation_analysis(station_id, db, hours=hours)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/task1", tags=["Task 1 — Fluctuation"])
def task1_bulk(state: Optional[str]=Query(None), district: Optional[str]=Query(None), hours: int=Query(720), db: Session=Depends(get_db)):
    results = get_fluctuation_analysis_batch(db, state=state, district=district, hours=hours)
    if not results: raise HTTPException(404, "No data found")
    return results


@router.get("/task2/{station_id}", tags=["Task 2 — Recharge"])
def task2_station(station_id: str, days: int=Query(365), db: Session=Depends(get_db)):
    result = get_recharge_estimate(station_id, db, days=days)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/task2", tags=["Task 2 — Recharge"])
def task2_bulk(state: Optional[str]=Query(None), district: Optional[str]=Query(None), days: int=Query(365), db: Session=Depends(get_db)):
    results = get_recharge_batch(db, state=state, district=district, days=days)
    if not results: raise HTTPException(404, "No data found")
    return results


@router.get("/task3/{station_id}", tags=["Task 3 — Evaluation"])
def task3_station(station_id: str, days: int=Query(365), stage_of_dev: Optional[float]=Query(None), db: Session=Depends(get_db)):
    result = get_station_evaluation(station_id, db, days=days, stage_of_dev=stage_of_dev)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/alerts", tags=["Alerts"])
def active_alerts(state: Optional[str]=Query(None), district: Optional[str]=Query(None), hours: int=Query(48), db: Session=Depends(get_db)):
    alerts = get_active_alerts(db, state=state, district=district, days=hours // 24 or 2)
    return {"total": len(alerts), "alerts": alerts}


@router.get("/alerts/anomalies", tags=["Alerts"])
def anomaly_alerts(state: Optional[str]=Query(None), hours: int=Query(24), db: Session=Depends(get_db)):
    anomalies = get_anomalies(db, state=state, hours=hours)
    return {"total": len(anomalies), "anomalies": anomalies}


@router.get("/summary/{state}", tags=["Scorecards"])
def state_summary(state: str, db: Session=Depends(get_db)):
    result = get_state_scorecard(state, db)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/summary/{state}/{district}", tags=["Scorecards"])
def district_summary(state: str, district: str, db: Session=Depends(get_db)):
    result = get_district_scorecard(state, district, db)
    if result.get("error"): raise HTTPException(404, result["error"])
    return result


@router.get("/ranking/states", tags=["Ranking"])
def state_ranking(db: Session=Depends(get_db)):
    rows = (
        db.query(
            Station.state,
            func.count(Station.station_id.distinct()).label("total_stations"),
            func.avg(DWLRReading.water_level_m).label("avg_level"),
            func.min(DWLRReading.water_level_m).label("min_level"),
            func.max(DWLRReading.water_level_m).label("max_level"),
        )
        .join(DWLRReading, Station.station_id == DWLRReading.station_id)
        .filter(Station.state.isnot(None))
        .group_by(Station.state)
        .all()
    )
    results = []
    for row in rows:
        if not row.state or not row.avg_level: continue
        avg = float(row.avg_level)
        status = "safe" if avg < 8 else "semi_critical" if avg < 15 else "critical" if avg < 25 else "over_exploited"
        rai = round(max(0, min(100, 100 - (avg / 80) * 100)), 1)
        results.append({
            "state": row.state, "total_stations": int(row.total_stations),
            "avg_water_level_m": round(avg, 2),
            "min_water_level_m": round(float(row.min_level), 2) if row.min_level else None,
            "max_water_level_m": round(float(row.max_level), 2) if row.max_level else None,
            "status": status, "rai": rai,
        })
    results.sort(key=lambda x: x["rai"])
    return {"total_states": len(results), "states": results}


@router.get("/ranking/districts/{state}", tags=["Ranking"])
def district_ranking(state: str, db: Session=Depends(get_db)):
    rows = (
        db.query(
            Station.district,
            func.count(Station.station_id.distinct()).label("total_stations"),
            func.avg(DWLRReading.water_level_m).label("avg_level"),
        )
        .join(DWLRReading, Station.station_id == DWLRReading.station_id)
        .filter(Station.state.ilike(f"%{state}%"))
        .filter(Station.district.isnot(None))
        .group_by(Station.district)
        .all()
    )
    results = []
    for row in rows:
        if not row.district or not row.avg_level: continue
        avg = float(row.avg_level)
        status = "safe" if avg < 8 else "semi_critical" if avg < 15 else "critical" if avg < 25 else "over_exploited"
        rai = round(max(0, min(100, 100 - (avg / 80) * 100)), 1)
        results.append({"district": row.district, "total_stations": int(row.total_stations), "avg_water_level_m": round(avg, 2), "status": status, "rai": rai})
    results.sort(key=lambda x: x["rai"])
    return {"state": state, "total_districts": len(results), "districts": results}


# ── EXPORT: summary MUST come before {station_id} to avoid route conflict ──
@router.get("/export/summary/csv", tags=["Export"])
def export_summary_csv(db: Session=Depends(get_db)):
    """Export all stations — MUST be defined before /export/{station_id}/csv"""
    stations = db.query(Station).all()
    if not stations: raise HTTPException(404, "No stations")
    latest = db.query(DWLRReading.station_id, func.avg(DWLRReading.water_level_m).label("avg_level")).group_by(DWLRReading.station_id).all()
    latest_map = {r.station_id: float(r.avg_level) for r in latest if r.avg_level}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["station_id","station_name","state","district","block","latitude","longitude","aquifer_type","well_depth_m","avg_water_level_m","cgwb_status"])
    for s in stations:
        avg = latest_map.get(s.station_id)
        status = "no_data" if avg is None else "safe" if avg < 8 else "semi_critical" if avg < 15 else "critical" if avg < 25 else "over_exploited"
        w.writerow([s.station_id, s.station_name, s.state, s.district, s.block, s.latitude, s.longitude, s.aquifer_type, s.well_depth_m, round(avg,2) if avg else "", status])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=subterra_all_stations.csv"})


@router.get("/export/{station_id}/csv", tags=["Export"])
def export_readings_csv(station_id: str, limit: int=Query(5000), db: Session=Depends(get_db)):
    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station: raise HTTPException(404, f"Station {station_id} not found")
    rows = db.query(DWLRReading).filter(DWLRReading.station_id == station_id).order_by(DWLRReading.timestamp).limit(limit).all()
    if not rows: raise HTTPException(404, "No readings to export")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["station_id","station_name","state","district","timestamp","water_level_m","data_quality_flag","is_anomaly","anomaly_reason"])
    for r in rows:
        w.writerow([station.station_id, station.station_name, station.state, station.district, r.timestamp.isoformat() if r.timestamp else "", r.water_level_m, r.data_quality_flag, r.is_anomaly, r.anomaly_reason or ""])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={station_id}_{station.state}_readings.csv"})
