"""
Core event schema. All events entering the system must conform to this model.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import json


class EventCategory(str, Enum):
    air_alert       = "air_alert"
    ground_strike   = "ground_strike"
    troop_movement  = "troop_movement"
    naval_event     = "naval_event"
    explosion       = "explosion"
    casualty_report = "casualty_report"
    unknown         = "unknown"


class LocationEntity(BaseModel):
    raw_text:   str
    normalized: Optional[str] = None
    lat:        Optional[float] = None
    lon:        Optional[float] = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class ConflictIntel(BaseModel):
    # ── Core fields ──────────────────────────────────────
    category:        EventCategory = EventCategory.unknown
    confidence:      float = Field(default=0.5, ge=0, le=1)
    raw_text:        str = ""
    translation:     str = ""
    source_language: str = "unknown"

    # ── Entities ─────────────────────────────────────────
    locations:          list[LocationEntity] = []
    weapons_mentioned:  list[str] = []
    unit_mentions:      list[str] = []
    casualty_count:     Optional[int] = None
    is_confirmed:       bool = False

    # ── DST confidence fields ─────────────────────────────
    bel:          float = 0.0    # Belief lower bound
    pl:           float = 1.0    # Plausibility upper bound
    conflict_k:   float = 0.0   # Conflict factor (0=none, 1=total)
    source_alpha: float = 0.5   # Source reliability weight

    # ── Fusion status ─────────────────────────────────────
    verified:      bool = False
    verified_by:   Optional[str] = None
    fusion_status: str = "SINGLE_SOURCE"  # FUSED | UNCERTAIN | CONFLICT_ALERT

    # ── Satellite imagery ─────────────────────────────────
    satellite_quicklook: Optional[str] = None

    def entities_json(self) -> str:
        return json.dumps({
            "weapons":    self.weapons_mentioned,
            "units":      self.unit_mentions,
            "casualties": self.casualty_count,
            "confirmed":  self.is_confirmed,
            "language":   self.source_language,
        })

    @property
    def lat(self) -> Optional[float]:
        return self.locations[0].lat if self.locations else None

    @property
    def lon(self) -> Optional[float]:
        return self.locations[0].lon if self.locations else None

    @property
    def location_name(self) -> Optional[str]:
        return self.locations[0].normalized if self.locations else None
