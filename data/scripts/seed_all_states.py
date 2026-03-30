"""
Run this ONCE to seed all 325 stations with 1 year of readings.
Place at: data/scripts/seed_all_states.py
Run: python seed_all_states.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

from db.database import SessionLocal
from app.models.station import Station, DWLRReading
from sqlalchemy import text, func
import random
from datetime import datetime, timedelta, timezone

db = SessionLocal()

# Get states with NO readings
print("Checking which states need seeding...")
states_with_data = set(
    r[0] for r in db.execute(text(
        "SELECT DISTINCT s.state FROM stations s "
        "JOIN dwlr_readings r ON s.station_id = r.station_id"
    )).fetchall()
)
all_states = set(r[0] for r in db.execute(text("SELECT DISTINCT state FROM stations WHERE state IS NOT NULL")).fetchall())
missing = all_states - states_with_data
print(f"States with data: {states_with_data}")
print(f"States missing data: {missing}")

base_levels = {
    "Rajasthan": 18.0, "Gujarat": 22.0, "Maharashtra": 8.0,
    "Uttar Pradesh": 6.0, "Punjab": 12.0, "Haryana": 11.0,
    "Bihar": 7.0, "Madhya Pradesh": 14.0, "Karnataka": 9.0,
    "Telangana": 16.0, "Andhra Pradesh": 13.0, "Tamil Nadu": 10.0,
    "West Bengal": 5.0, "Odisha": 8.0, "Chhattisgarh": 11.0,
    "Jharkhand": 9.0, "Uttarakhand": 12.0, "Himachal Pradesh": 15.0,
    "Assam": 6.0, "Kerala": 7.0, "Goa": 8.0,
}

end_date   = datetime.now(timezone.utc)
start_date = end_date - timedelta(days=365)
total_inserted = 0

for state in missing:
    stations = db.execute(text(
        "SELECT station_id FROM stations WHERE state = :s"
    ), {"s": state}).fetchall()
    
    base = base_levels.get(state, 12.0)
    print(f"Seeding {state}: {len(stations)} stations...")
    
    for (station_id,) in stations:
        wl = base + random.uniform(-3, 3)
        ts = start_date
        rows = []
        while ts < end_date:
            month = ts.month
            drift = random.uniform(-0.05, 0.01) if month in [7,8,9] else random.uniform(-0.02, 0.04)
            wl = round(max(0.5, min(150, wl + drift)), 2)
            rows.append({
                "station_id": station_id, "timestamp": ts,
                "water_level_m": wl, "data_quality_flag": "G",
                "is_anomaly": False, "anomaly_reason": ""
            })
            ts += timedelta(minutes=15)
            if len(rows) >= 3000:
                db.execute(text("""
                    INSERT INTO dwlr_readings (station_id,timestamp,water_level_m,data_quality_flag,is_anomaly,anomaly_reason)
                    VALUES (:station_id,:timestamp,:water_level_m,:data_quality_flag,:is_anomaly,:anomaly_reason)
                    ON CONFLICT DO NOTHING
                """), rows)
                db.commit()
                total_inserted += len(rows)
                rows = []
        if rows:
            db.execute(text("""
                INSERT INTO dwlr_readings (station_id,timestamp,water_level_m,data_quality_flag,is_anomaly,anomaly_reason)
                VALUES (:station_id,:timestamp,:water_level_m,:data_quality_flag,:is_anomaly,:anomaly_reason)
                ON CONFLICT DO NOTHING
            """), rows)
            db.commit()
            total_inserted += len(rows)

print(f"\nDone! Inserted {total_inserted:,} readings")
total = db.execute(text("SELECT COUNT(*) FROM dwlr_readings")).fetchone()[0]
states_now = db.execute(text("SELECT COUNT(DISTINCT s.state) FROM stations s JOIN dwlr_readings r ON s.station_id=r.station_id")).fetchone()[0]
print(f"Total readings: {total:,}")
print(f"States with data: {states_now}")
db.close()