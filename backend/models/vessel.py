"""
Vessel (AIS) model schema.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class Vessel(BaseModel):
    mmsi:        str
    name:        Optional[str] = None
    lat:         float
    lon:         float
    heading:     Optional[float] = None
    speed_kts:   Optional[float] = None
    vessel_type: Optional[str] = None
    flag:        Optional[str] = None
    last_seen:   Optional[datetime] = None
