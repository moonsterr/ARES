"""
Aircraft model schema.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class Aircraft(BaseModel):
    icao_hex:    str
    callsign:    Optional[str] = None
    lat:         float
    lon:         float
    altitude_ft: Optional[int] = None
    heading:     Optional[float] = None
    speed_kts:   Optional[float] = None
    ac_type:     Optional[str] = None
    reg:         Optional[str] = None
    last_seen:   Optional[datetime] = None
