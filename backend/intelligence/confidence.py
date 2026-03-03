"""
Dempster-Shafer Theory + PCR5 Confidence Engine
================================================
Frame of discernment Θ for location fusion:
  Θ = {Zone_A, Zone_B, ..., Zone_N, UNKNOWN}

Each source produces a Basic Belief Assignment (BBA):
  m: 2^Θ → [0,1],  m(∅)=0,  Σ m(A)=1

Combination rule: PCR5 (Dezert-Smarandanche 2006)
PCR5 redistributes conflicting mass back to the
conflicting hypotheses in proportion to their mass values,
rather than the renormalization in Dempster's original rule
(which causes Zadeh's paradox on high-conflict inputs).

Reference:
  Dezert, J. & Smarandanche, F. (2006).
  "A new probabilistic transformation of belief mass assignment"
  Fusion 2006 Conference.
"""
from __future__ import annotations
from typing import Dict, Tuple
import math

# Type alias: BBA maps frozenset[str] → float
BBA = Dict[frozenset, float]


def discount_bba(bba: BBA, alpha: float) -> BBA:
    """
    Reliability discounting (Shafer 1976).
    Scales all non-universal-set masses by α.
    Transfers (1-α) mass to the universal set (total ignorance).

    alpha=1.0 → fully trust the source
    alpha=0.0 → source adds no information (all mass on Θ)
    """
    theta = frozenset(["UNKNOWN"])  # represents full ignorance / Θ
    discounted: BBA = {}
    for focal_elem, mass in bba.items():
        if focal_elem == theta:
            discounted[focal_elem] = discounted.get(theta, 0.0) + mass
        else:
            discounted[focal_elem] = mass * alpha

    discounted[theta] = discounted.get(theta, 0.0) + (1.0 - alpha) * sum(
        m for k, m in bba.items() if k != theta
    )
    # Normalize (floating point safety)
    total = sum(discounted.values())
    return {k: v / total for k, v in discounted.items()}


def pcr5_combine(m1: BBA, m2: BBA) -> Tuple[BBA, float]:
    """
    PCR5 combination of two BBAs.
    Returns (combined_bba, conflict_factor_K).

    PCR5 formula for two sources:
      For each pair (A, B) where A ∩ B = ∅:
        Conflicting mass c(A,B) = m1(A) * m2(B)
        Redistribute:
          m_pcr5(A) += c(A,B) * m1(A) / (m1(A) + m2(B))
          m_pcr5(B) += c(A,B) * m2(B) / (m1(A) + m2(B))

    For non-conflicting pairs (A ∩ B ≠ ∅):
      m_pcr5(A ∩ B) += m1(A) * m2(B)
    """
    combined: BBA = {}
    conflict_k = 0.0

    for A in m1:
        for B in m2:
            mass_ab = m1[A] * m2[B]
            intersection = A & B

            if intersection:
                # Consistent evidence — mass goes to the intersection
                combined[intersection] = combined.get(intersection, 0.0) + mass_ab
            else:
                # Conflicting evidence — PCR5 redistribution
                conflict_k += mass_ab
                denom = m1[A] + m2[B]
                if denom > 1e-10:
                    # Redistribute proportionally back to each conflicting source
                    combined[A] = combined.get(A, 0.0) + mass_ab * m1[A] / denom
                    combined[B] = combined.get(B, 0.0) + mass_ab * m2[B] / denom

    # Normalize
    total = sum(combined.values())
    if total > 1e-10:
        combined = {k: v / total for k, v in combined.items()}

    return combined, conflict_k


def belief(bba: BBA, hypothesis: frozenset) -> float:
    """Bel(A) = Σ m(B) for all B ⊆ A"""
    return sum(m for B, m in bba.items() if B and B.issubset(hypothesis))


def plausibility(bba: BBA, hypothesis: frozenset) -> float:
    """Pl(A) = Σ m(B) for all B where B ∩ A ≠ ∅"""
    return sum(m for B, m in bba.items() if B & hypothesis)


def location_to_bba(lat: float, lon: float, location_name: str,
                    base_confidence: float = 0.8) -> BBA:
    """
    Convert a geocoded location to a BBA over the frame of discernment.
    The frame is dynamically constructed from the locations being compared.
    Returns a BBA with mass on the named location and residual on UNKNOWN.
    """
    loc_key = frozenset([location_name or f"{lat:.3f},{lon:.3f}"])
    unknown = frozenset(["UNKNOWN"])
    residual = 1.0 - base_confidence
    return {
        loc_key: base_confidence,
        unknown: residual,
    }


def initial_bba(intel, alpha: float) -> dict:
    """
    Create the initial BBA for a single Telegram message.
    Returns belief, plausibility, and conflict_k for display.
    Used before cross-source fusion.
    """
    if not intel.locations:
        return {"belief": 0.0, "plausibility": 1.0, "conflict_k": 0.0}

    loc = intel.locations[0]
    raw_bba = location_to_bba(
        lat=loc.lat or 0,
        lon=loc.lon or 0,
        location_name=loc.normalized or loc.raw_text,
        base_confidence=intel.confidence,
    )
    discounted = discount_bba(raw_bba, alpha)
    h = frozenset([loc.normalized or loc.raw_text or "target"])
    return {
        "belief":       belief(discounted, h),
        "plausibility": plausibility(discounted, h),
        "conflict_k":   0.0,   # no conflict yet (single source)
    }


def fuse_two_sources(
    loc1_name: str, lat1: float, lon1: float, conf1: float, alpha1: float,
    loc2_name: str, lat2: float, lon2: float, conf2: float, alpha2: float,
) -> dict:
    """
    Fuse two conflicting location reports using PCR5.
    Returns the fusion result with conflict factor K.

    If K < 0.3  → safe to emit fused coordinate
    If 0.3 ≤ K < 0.5 → UNCERTAIN, emit both candidates
    If K ≥ 0.5  → CONFLICT_ALERT, do not fuse, report both
    """
    bba1_raw = location_to_bba(lat1, lon1, loc1_name, conf1)
    bba2_raw = location_to_bba(lat2, lon2, loc2_name, conf2)

    bba1 = discount_bba(bba1_raw, alpha1)
    bba2 = discount_bba(bba2_raw, alpha2)

    combined, K = pcr5_combine(bba1, bba2)

    h1 = frozenset([loc1_name])
    h2 = frozenset([loc2_name])

    bel1 = belief(combined, h1)
    pl1  = plausibility(combined, h1)
    bel2 = belief(combined, h2)
    pl2  = plausibility(combined, h2)

    # Determine fusion status
    if K >= 0.5:
        status = "CONFLICT_ALERT"
        # Use the higher-belief location as the display point
        if bel1 >= bel2:
            fused_lat, fused_lon = lat1, lon1
            fused_name = loc1_name
        else:
            fused_lat, fused_lon = lat2, lon2
            fused_name = loc2_name
    elif K >= 0.3:
        status = "UNCERTAIN"
        # Inverse-variance weighted centroid as fallback
        w1 = alpha1 * conf1
        w2 = alpha2 * conf2
        total_w = w1 + w2
        fused_lat  = (lat1 * w1 + lat2 * w2) / total_w
        fused_lon  = (lon1 * w1 + lon2 * w2) / total_w
        fused_name = f"{loc1_name} / {loc2_name}"
    else:
        status = "FUSED"
        w1 = alpha1 * conf1 * bel1
        w2 = alpha2 * conf2 * bel2
        total_w = w1 + w2 if (w1 + w2) > 0 else 1.0
        fused_lat  = (lat1 * w1 + lat2 * w2) / total_w
        fused_lon  = (lon1 * w1 + lon2 * w2) / total_w
        fused_name = loc1_name if bel1 >= bel2 else loc2_name

    # Haversine distance between the two reports (diagnostic)
    dist_km = haversine_km(lat1, lon1, lat2, lon2)

    return {
        "status":     status,
        "conflict_k": round(K, 4),
        "fused_lat":  round(fused_lat, 6),
        "fused_lon":  round(fused_lon, 6),
        "fused_name": fused_name,
        "source1": {"name": loc1_name, "bel": round(bel1, 4), "pl": round(pl1, 4)},
        "source2": {"name": loc2_name, "bel": round(bel2, 4), "pl": round(pl2, 4)},
        "distance_between_reports_km": round(dist_km, 2),
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in kilometers between two WGS84 coordinates."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
