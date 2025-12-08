# environment_model.py
"""
Environment model for railway network:
- Exposes functions to generate environment parameters for STATIONS and TRACK SEGMENTS.
- Parameters p81..p100 (20 parameters) are produced deterministically from an id + optional seed.
- Values are normalized to meaningful ranges (most 0..1) but comments indicate interpretation.
- Designed to be a local test/stub that you can later replace with sensor/db-backed logic.

Usage:
    from environment_model import generate_station_environment, generate_segment_environment
"""

from typing import Dict
import hashlib
import math
import random

# ============================================================
# Helpers
# ============================================================

def _seeded_random(seed_str: str) -> random.Random:
    """Return a Random instance seeded deterministically from seed_str."""
    s = str(seed_str)  # ensure safe type
    h = hashlib.sha256(s.encode("utf-8")).digest()
    seed_int = int.from_bytes(h[:8], "big")
    return random.Random(seed_int)

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

def _norm_to_range(rnd: random.Random, lo: float, hi: float) -> float:
    return lo + (hi - lo) * rnd.random()

# ============================================================
# Station environment generator (p81–p100)
# ============================================================

def generate_station_environment(station_name: str, seed_extra: str = "") -> Dict[str, float]:
    """
    Return p81..p100 for a station.
    Deterministic: same station_name + seed_extra => same values.
    """
    station_name = str(station_name)
    seed_extra = str(seed_extra)

    rnd = _seeded_random(f"station::{station_name}::{seed_extra}")

    base = rnd.random()
    seasonal = rnd.random()
    human = rnd.random()

    p81 = _clamp(0.25 * base + 0.25 * rnd.random() + 0.3 * rnd.random())
    p82 = _clamp(0.15 * base + 0.6 * rnd.random())
    p83 = _clamp(0.1 * seasonal + 0.8 * rnd.random())
    p84 = _clamp(0.2 * rnd.random())
    p85 = _clamp(0.4 * seasonal + 0.5 * rnd.random())
    p86 = _clamp(0.2 * rnd.random() + 0.6 * (rnd.random() * 0.5))
    p87 = _clamp(0.2 * rnd.random() + 0.1 * human)
    p88 = _clamp(0.35 * rnd.random())
    p89 = _clamp(0.1 * rnd.random())
    p90 = _clamp(0.05 * rnd.random())
    p91 = _clamp(0.2 * seasonal + 0.4 * rnd.random())
    p92 = _clamp(0.3 * rnd.random())
    p93 = _clamp(0.2 * rnd.random())
    p94 = _clamp(0.2 * human + 0.2 * rnd.random())
    p95 = _clamp(0.25 * rnd.random())
    p96 = _clamp(0.6 * rnd.random() if rnd.random() > 0.5 else 0.15 * rnd.random())
    p97 = _clamp(0.2 * rnd.random() + 0.6 * human)
    p98 = _clamp(0.2 * rnd.random() + 0.5 * human)
    p99 = _clamp(0.3 * rnd.random())
    p100 = _clamp(0.15 * rnd.random())

    return {
        "p81": p81, "p82": p82, "p83": p83, "p84": p84, "p85": p85,
        "p86": p86, "p87": p87, "p88": p88, "p89": p89, "p90": p90,
        "p91": p91, "p92": p92, "p93": p93, "p94": p94, "p95": p95,
        "p96": p96, "p97": p97, "p98": p98, "p99": p99, "p100": p100
    }

# ============================================================
# Segment environment generator (p81–p100, per 100m)
# ============================================================

def generate_segment_environment(segment_id: str, distance_meters: float = 100.0, seed_extra: str = "") -> Dict[str, float]:
    """
    Generate environment parameters for a track segment (typically 100m).
    Deterministic based on segment_id.
    """
    segment_id = str(segment_id)
    seed_extra = str(seed_extra)

    rnd = _seeded_random(f"segment::{segment_id}::{seed_extra}")

    local_factor = (
        int(hashlib.sha256(segment_id.encode("utf-8")).hexdigest()[:8], 16) % 1000
    ) / 1000.0

    def n(scale=1.0):
        return (rnd.random() - 0.5) * 2.0 * scale

    p81 = _clamp(0.3 * _norm_to_range(rnd, 0, 1) + 0.4 * local_factor + 0.2 * (n(0.5) + 0.5))
    p82 = _clamp(0.25 * local_factor + 0.6 * rnd.random() + 0.1 * (distance_meters / 100.0))
    p83 = _clamp(0.1 * rnd.random() + 0.8 * ((local_factor + rnd.random()) / 2.0))
    p84 = _clamp(0.5 * local_factor + 0.4 * rnd.random())
    p85 = _clamp(0.4 * rnd.random() + 0.4 * local_factor)
    p86 = _clamp(0.2 * rnd.random() + 0.6 * local_factor * rnd.random())
    p87 = _clamp(0.5 * rnd.random() + 0.5 * (1.0 - local_factor))
    p88 = _clamp(0.2 * rnd.random() + (0.8 if "curve" in segment_id.lower() else 0.0) + 0.1 * local_factor)
    p89 = _clamp(abs(n(0.2)) + 0.05 * local_factor)
    p90 = _clamp(0.05 * rnd.random() + 0.2 * local_factor)
    p91 = _clamp((p84 * 0.5) + (p85 * 0.4) + 0.1 * rnd.random())
    p92 = _clamp(0.2 * rnd.random() + 0.4 * (local_factor * 0.5))
    p93 = _clamp(0.3 * rnd.random() + 0.4 * (1.0 - local_factor))
    p94 = _clamp(0.2 * rnd.random() + 0.3 * local_factor)
    p95 = _clamp(0.3 * rnd.random())
    p96 = _clamp(0.4 * rnd.random() + (0.6 if (int(hashlib.sha256(segment_id.encode()).hexdigest()[-1], 16) % 3 == 0) else 0.0))
    p97 = _clamp(0.25 * rnd.random() + 0.6 * (1.0 - local_factor))
    p98 = _clamp(0.3 * rnd.random() + 0.4 * (1.0 - local_factor))
    p99 = _clamp(0.25 * rnd.random() + 0.6 * local_factor)
    p100 = _clamp(0.25 * rnd.random() + 0.5 * p84 + 0.2 * (1.0 - local_factor))

    return {
        "p81": p81, "p82": p82, "p83": p83, "p84": p84, "p85": p85,
        "p86": p86, "p87": p87, "p88": p88, "p89": p89, "p90": p90,
        "p91": p91, "p92": p92, "p93": p93, "p94": p94, "p95": p95,
        "p96": p96, "p97": p97, "p98": p98, "p99": p99, "p100": p100
    }

# ============================================================
# Segmenting a full track line into 100m chunks
# ============================================================

def segment_line_between(stations: Dict[str, Dict[str, float]], u: str, v: str, segment_length_m: float = 100.0):
    """
    Generate segments between stations u and v, each with p81–p100.
    Safe string casting added for Pylance.
    """
    u = str(u)
    v = str(v)

    if u not in stations or v not in stations:
        raise KeyError(f"Station missing: {u} or {v}")

    a = stations[str(u)]
    b = stations[str(v)]

    lat1, lon1 = a["lat"], a["lon"]
    lat2, lon2 = b["lat"], b["lon"]

    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    s1 = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
          math.sin(dlon / 2) ** 2
    )
    distance_m = 2 * R * math.asin(math.sqrt(max(0.0, s1)))

    num_segments = max(1, int(math.ceil(distance_m / max(1.0, segment_length_m))))
    segments = []

    for i in range(num_segments):
        t0 = i / num_segments
        t1 = (i + 1) / num_segments

        sx = lat1 + (lat2 - lat1) * t0
        sy = lon1 + (lon2 - lon1) * t0
        ex = lat1 + (lat2 - lat1) * t1
        ey = lon1 + (lon2 - lon1) * t1

        seg_id = f"{u}-{v}-{i}"
        env = generate_segment_environment(seg_id, distance_meters=segment_length_m)

        segments.append({
            "id": seg_id,
            "start": {"lat": sx, "lon": sy},
            "end": {"lat": ex, "lon": ey},
            "env": env
        })

    return segments
