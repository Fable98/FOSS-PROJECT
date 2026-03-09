"""
models/station.py — SubTerra ORM Models
SQLAlchemy models for Station master and DWLR readings.
These are used by FastAPI routes; the pipeline writes directly via psycopg2.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Boolean, Date,
    DateTime, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Station(Base):
    """Static metadata for each DWLR station."""
    __tablename__ = "stations"

    station_id   = Column(String, primary_key=True)
    station_name = Column(String)
    latitude     = Column(Float, nullable=False)
    longitude    = Column(Float, nullable=False)
    state        = Column(String)
    district     = Column(String)
    block        = Column(String)
    well_depth_m = Column(Float)
    aquifer_type = Column(String)
    updated_at   = Column(DateTime(timezone=True), default=datetime.utcnow)

    def to_dict(self):
        return {
            "station_id":   self.station_id,
            "station_name": self.station_name,
            "latitude":     self.latitude,
            "longitude":    self.longitude,
            "state":        self.state,
            "district":     self.district,
            "block":        self.block,
            "well_depth_m": self.well_depth_m,
            "aquifer_type": self.aquifer_type,
        }


class DWLRReading(Base):
    """15-minute DWLR sensor reading (TimescaleDB hypertable)."""
    __tablename__ = "dwlr_readings"

    station_id        = Column(String,  primary_key=True)
    timestamp         = Column(DateTime(timezone=True), primary_key=True)
    water_level_m     = Column(Float)
    data_quality_flag = Column(String,  default="G")
    is_anomaly        = Column(Boolean, default=False)
    anomaly_reason    = Column(Text,    default="")


class Rainfall(Base):
    """Daily district-level rainfall from IMD."""
    __tablename__ = "rainfall"
    __table_args__ = (
        UniqueConstraint("state", "district", "date"),
    )

    state        = Column(String, primary_key=True)
    district     = Column(String, primary_key=True)
    date         = Column(Date,   primary_key=True)
    rainfall_mm  = Column(Float)