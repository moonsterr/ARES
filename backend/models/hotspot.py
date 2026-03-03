"""
NASA FIRMS thermal hotspot model schema.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class Hotspot(BaseModel):
    lat:         float
    lon:         float
    source:      str              # VIIRS_SNPP_NRT | MODIS_NRT
    brightness:  Optional[float] = None
    frp:         Optional[float] = None  # Fire Radiative Power in MW
    confidence:  str = "nominal"         # low | nominal | high
    detected_at: Optional[datetime] = None
