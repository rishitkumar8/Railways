# computeSafetyParameters.py
"""
P121–P140 — Safety, Weather & Human Factor Parameters
Each train receives p121..p140 in 0..1 (higher = worse).
Inputs expected:
    t = {
        id,
        speed,
        status,
        path,
        lat, lon,
        driver_fatigue (0..1),
        visibility_m (optional),
        weather_data (dict) optional => { rain_mm, wind_kmh, temp_c, humidity_pct }
        spad_events (int),
        emergency_brake_count (int),
        signal_quality (0..1),
        noise_dba (float),
        vibration_rms (float),
        track_curvature_risk (float)
    }

This module is resilient to missing fields and generates deterministic fallback values.
"""

import hashlib
import math
from typing import List, Dict

# ---------------------------
# Helpers
# ---------------------------

def _seed_from_str(s: str) -> int:
    return int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:8], "big")

def _rand01(seed: int) -> float:
    return (seed % 100003) / 100003.0

def _clamp01(x: float) -> float:
    if x != x:
        return 0.0
    return max(0.0, min(1.0, x))

def _safe_div(a, b, d=0.0):
    try:
        return a / b
    except:
        return d


# ---------------------------
# Main Function
# ---------------------------

def compute_safety_parameters(
    trains: List[Dict],
    edges: List[Dict] = None
) -> Dict[str, Dict[str, float]]:

    results: Dict[str, Dict[str, float]] = {}

    for t in trains:
        tid = t.get("id", None)
        if tid is None or tid == "":
            continue
        seed = _seed_from_str(tid)
        rnd = _rand01(seed)

        speed = float(t.get("speed", 0.0))
        status = t.get("status", "RUNNING")
        driver_fatigue = float(t.get("driver_fatigue", 0.2))

        # weather data optional
        weather = t.get("weather_data", {})
        rain_mm = float(weather.get("rain_mm", rnd * 20.0))        # 0..20mm fallback
        wind_kmh = float(weather.get("wind_kmh", rnd * 40.0))      # 0..40 km/h fallback
        temp_c = float(weather.get("temp_c", 20 + rnd * 15))
        humidity = float(weather.get("humidity_pct", 50 + rnd * 40))

        visibility_m = float(t.get("visibility_m", max(50.0, 2000 - rain_mm * 40.0)))
        signal_quality = float(t.get("signal_quality", 1.0 - rnd * 0.3))

        spad_events = int(t.get("spad_events", 0))
        emergency_brakes = int(t.get("emergency_brake_count", 0))

        noise_dba = float(t.get("noise_dba", 70 + rnd * 10))
        vibration_rms = float(t.get("vibration_rms", 0.2))
        curvature_risk = float(t.get("track_curvature_risk", rnd * 0.3))

        # ---------------------------------------------------
        # P121 — SPAD probability (Signal Passed At Danger)
        # influenced by speed, fatigue, signal quality
        # ---------------------------------------------------
        p121 = _clamp01(
            0.5 * _clamp01(speed / 160.0) +
            0.3 * driver_fatigue +
            0.2 * (1.0 - signal_quality)
        )

        # ---------------------------------------------------
        # P122 — Visibility risk (fog, rain, night)
        # map visibility: 2000m->0 risk, 50m->1 risk
        # ---------------------------------------------------
        p122 = _clamp01(1.0 - _safe_div(visibility_m, 2000.0))

        # ---------------------------------------------------
        # P123 — Wind hazard (crosswind derail/toppling risk)
        # normal trains safe until ~50-70km/h winds
        # ---------------------------------------------------
        p123 = _clamp01(wind_kmh / 70.0)

        # ---------------------------------------------------
        # P124 — Rainfall slip risk
        # 0..20mm = linear map; >20 saturates
        # ---------------------------------------------------
        p124 = _clamp01(rain_mm / 20.0)

        # ---------------------------------------------------
        # P125 — Temperature extreme hazard
        # safe band: 5°C–45°C
        # ---------------------------------------------------
        if temp_c < 5:
            p125 = _clamp01((5 - temp_c) / 20.0)
        elif temp_c > 45:
            p125 = _clamp01((temp_c - 45) / 20.0)
        else:
            p125 = 0.0

        # ---------------------------------------------------
        # P126 — SPAD history factor
        # ---------------------------------------------------
        p126 = _clamp01(spad_events / 10.0)

        # ---------------------------------------------------
        # P127 — Emergency braking frequency risk
        # ---------------------------------------------------
        p127 = _clamp01(emergency_brakes / 20.0)

        # ---------------------------------------------------
        # P128 — Signal/communication degradation
        # ---------------------------------------------------
        p128 = _clamp01(1.0 - signal_quality)

        # ---------------------------------------------------
        # P129 — Human factor risk (fatigue, stress)
        # ---------------------------------------------------
        p129 = _clamp01(driver_fatigue)

        # ---------------------------------------------------
        # P130 — Noise/vibration related hazard
        # 70–100 dBA → map 0..1
        # vibration_rms 0..2 m/s² → map 0..1
        # ---------------------------------------------------
        noise_risk = _clamp01((noise_dba - 70.0) / 30.0)
        vib_risk = _clamp01(vibration_rms / 2.0)
        p130 = _clamp01(0.6 * noise_risk + 0.4 * vib_risk)

        # ---------------------------------------------------
        # P131 — Track curvature hazard (centrifugal + lateral)
        # curvature_risk already normalized 0..1 in input
        # ---------------------------------------------------
        p131 = _clamp01(curvature_risk)

        # ---------------------------------------------------
        # P132 — Track adhesion loss (rain + leaf + humidity)
        # ---------------------------------------------------
        p132 = _clamp01(0.5 * p124 + 0.3 * (humidity / 100.0) + 0.2 * rnd)

        # ---------------------------------------------------
        # P133 — Operational consistency risk
        # depends on stops, start patterns, status
        # ---------------------------------------------------
        status_factor = 1.0 if status == "EMERGENCY" else (0.5 if status == "DELAYED" else 0.2)
        p133 = _clamp01(0.6 * status_factor + 0.4 * driver_fatigue)

        # ---------------------------------------------------
        # P134 — Subsystem coordination (coupling signals, brake sync)
        # depends on signal quality + vibration + random deterministic
        # ---------------------------------------------------
        p134 = _clamp01(
            0.4 * (1.0 - signal_quality) +
            0.4 * vib_risk +
            0.2 * rnd
        )

        # ---------------------------------------------------
        # P135 — Environmental composite hazard
        # (wind + rain + temperature)
        # ---------------------------------------------------
        p135 = _clamp01(0.35 * p123 + 0.35 * p124 + 0.30 * p125)

        # ---------------------------------------------------
        # P136 — Operator situational awareness risk
        # inverse of visibility & signal clarity
        # ---------------------------------------------------
        p136 = _clamp01(0.6 * p122 + 0.4 * p128)

        # ---------------------------------------------------
        # P137 — Fatigue + workload fusion
        # ---------------------------------------------------
        p137 = _clamp01(0.5 * driver_fatigue + 0.5 * status_factor)

        # ---------------------------------------------------
        # P138 — Speed-weather combined hazard
        # ---------------------------------------------------
        speed_factor = _clamp01(speed / 160.0)
        p138 = _clamp01(0.5 * speed_factor + 0.5 * p135)

        # ---------------------------------------------------
        # P139 — System reliability degradation
        # depends on random wear + poor weather
        # ---------------------------------------------------
        p139 = _clamp01(0.5 * rnd + 0.5 * p135)

        # ---------------------------------------------------
        # P140 — Final Safety Composite Index
        # Weighted fusion of the most critical values
        # ---------------------------------------------------
        p140 = _clamp01(
            0.14 * p121 +
            0.12 * p122 +
            0.12 * p123 +
            0.12 * p124 +
            0.10 * p125 +
            0.10 * p129 +
            0.10 * p130 +
            0.10 * p135 +
            0.10 * p138
        )

        results[tid] = {
            "p121": p121, "p122": p122, "p123": p123, "p124": p124, "p125": p125,
            "p126": p126, "p127": p127, "p128": p128, "p129": p129, "p130": p130,
            "p131": p131, "p132": p132, "p133": p133, "p134": p134, "p135": p135,
            "p136": p136, "p137": p137, "p138": p138, "p139": p139, "p140": p140
        }

    return results
