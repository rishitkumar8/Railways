# computeCollisionParameters.py
"""
Collision Dynamics Parameters (P61..P80)

Usage:
    from computeCollisionParameters import compute_collision_parameters

    collision = compute_collision_parameters(trains, stations, edges)
    # collision is { trainId: { 'p61':..., ..., 'p80':... }, ... }

Notes:
- trains: list of dicts with at least: id, lat, lon, speed (km/h), path (list of station ids), progress (0..1)
- stations/edges are used for path/graph context but not strictly required
- All outputs normalized to 0..1 (higher = worse/higher risk), p80 is the composite collision score
"""

import math
from typing import List, Dict, Tuple
from collections import defaultdict

# -------------------------
# Helpers
# -------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    """Return distance in meters between two lat/lon points (approx)."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2.0)**2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))

def kmh_to_mps(v_kmh: float) -> float:
    return v_kmh / 3.6

def safe_div(a: float, b: float, default: float = 0.0) -> float:
    try:
        return a / b
    except Exception:
        return default

def clamp01(x: float) -> float:
    if x != x:  # NaN guard
        return 0.0
    return max(0.0, min(1.0, x))

# -------------------------
# Core function
# -------------------------
def compute_collision_parameters(
    trains: List[Dict],
    stations: List[Dict] = None,
    edges: List[Dict] = None,
    braking_decel_mps2: float = 0.8
) -> Dict[str, Dict[str, float]]:
    """
    Compute P61..P80 per train.

    Return structure:
      { train_id: { "p61":..., ... "p80": ... }, ... }
    """

    # quick lookup by id
    train_by_id = {t["id"]: t for t in trains}

    # precompute positions & speeds
    positions = {}
    speeds_mps = {}
    for t in trains:
        lat = t.get("lat", 0.0)
        lon = t.get("lon", 0.0)
        sp = float(t.get("speed", 0.0))
        positions[t["id"]] = (lat, lon)
        speeds_mps[t["id"]] = max(0.0, kmh_to_mps(sp))

    # Build edge-load mapping (undirected) for quick conflict checks
    edge_paths = defaultdict(int)
    for t in trains:
        path = t.get("path", [])
        for i in range(len(path)-1):
            a, b = path[i], path[i+1]
            key = tuple(sorted([a, b]))
            edge_paths[key] += 1

    # helper: estimated stopping distance (m) at speed with braking_decel_mps2
    def stopping_distance_m(v_mps: float, reaction_s: float = 1.5) -> float:
        d_reaction = v_mps * reaction_s
        d_brake = (v_mps**2) / (2.0 * max(1e-6, braking_decel_mps2))
        return d_reaction + d_brake

    # For each train compute local neighborhood metrics (nearest N trains)
    results = {}
    for t in trains:
        tid = t["id"]
        lat, lon = positions[tid]
        v = speeds_mps[tid]

        # Find nearest other trains (distance & relative speed)
        neighbors = []
        for ot in trains:
            if ot["id"] == tid: continue
            olat, olon = positions[ot["id"]]
            d = haversine_m(lat, lon, olat, olon)
            ov = speeds_mps[ot["id"]]
            rel_speed = v - ov  # positive = this train faster than other
            neighbors.append((d, ot["id"], rel_speed, ov))

        neighbors.sort(key=lambda x: x[0])
        nearest = neighbors[0] if neighbors else None

        # P61 — Proximity index (0..1) closer => higher
        p61 = 0.0
        if nearest:
            d0 = nearest[0]
            # proximity sigmoid: under 100m = high, over 2000m = low
            p61 = clamp01(1.0 - safe_div(d0 - 100.0, 1900.0))  # maps 100->1,2000->0

        # P62 — Relative speed risk (normalized)
        # high relative closing speed => higher risk
        p62 = 0.0
        if nearest:
            rel_v = abs(nearest[2])
            # normalize: 0..50 km/h closing => 0..1
            p62 = clamp01(rel_v / (50.0 / 3.6))  # note rel_v in m/s, convert denom m/s

        # P63 — Time-to-collision (TTC) normalized (lower TTC => higher risk)
        p63 = 0.0
        if nearest:
            d0 = max(1.0, nearest[0])
            rel_v = v - nearest[3]  # this - other (m/s)
            if rel_v > 0.1:  # closing
                ttc = d0 / rel_v
                # map 0..120s to 1..0 (shorter time => worse)
                p63 = clamp01(1.0 - safe_div(ttc, 120.0))
            else:
                p63 = 0.0

        # P64 — Braking margin (how close stopping distance is to actual distance)
        p64 = 0.0
        if nearest:
            d0 = max(1.0, nearest[0])
            stop_req = stopping_distance_m(v)
            # if stop_req >= d0 then p64 = 1 (no margin). else lower
            margin = safe_div(d0 - stop_req, max(1.0, d0))
            # invert: smaller margin => higher p64
            p64 = clamp01(1.0 - margin)

        # P65 — Head-on vs rear-end risk proxy
        # If relative direction indicated by path ordering implies opposite headings -> head-on risk
        p65 = 0.0
        if nearest:
            # crude check: do they share an edge (neighbor's id in path)
            this_path = t.get("path", [])
            other = train_by_id[nearest[1]]
            other_path = other.get("path", [])
            shared = False
            for i in range(len(this_path)-1):
                for j in range(len(other_path)-1):
                    a1, b1 = this_path[i], this_path[i+1]
                    a2, b2 = other_path[j], other_path[j+1]
                    if set([a1,b1]) == set([a2,b2]):
                        shared = True
                        # if they traverse edge in opposite directions (order differs)
                        if a1 == b2 and b1 == a2:
                            p65 = 1.0  # head-on high risk
                        else:
                            p65 = 0.4  # same direction rear/overlapping
                        break
                if shared: break

        # P66 — Track conflict index (shared edge load normalized)
        p66 = 0.0
        if len(t.get("path", [])) > 1:
            loads = []
            for i in range(len(t["path"])-1):
                a, b = t["path"][i], t["path"][i+1]
                key = tuple(sorted([a,b]))
                loads.append(edge_paths.get(key, 0))
            if loads:
                local_max = max(loads)
                # assume max possible load normalization by total trains
                p66 = clamp01(local_max / max(1.0, len(trains)))
            else:
                p66 = 0.0

        # P67 — Emergency brake need (binary-ish normalized)
        # high if stopping distance > nearest distance OR TTC very small
        p67 = 0.0
        if nearest:
            d0 = nearest[0]
            stop_req = stopping_distance_m(v, reaction_s=0.8)  # assume short reaction for emergency
            if stop_req >= d0 or (p63 > 0.8) or (p65 > 0.9):
                p67 = 1.0
            else:
                p67 = clamp01((stop_req / max(1.0, d0)) * 0.9)

        # P68 — Predicted overlap time (if both on same edge, estimate time both occupy common section)
        p68 = 0.0
        if nearest and p66 > 0.0:
            # rough: overlap length estimate 200m normalized by relative speed
            overlap_len = 200.0
            rel_v = max(0.1, abs(v - nearest[3]))
            t_overlap = overlap_len / rel_v
            # map 0..600s to 1..0
            p68 = clamp01(1.0 - safe_div(t_overlap, 600.0))

        # P69 — Lateral collision risk (derail/side collision) proxy
        # depends on speed + curvature/track info — use 0.2 * p66 + 0.8 * p61 as proxy
        p69 = clamp01(0.2 * p66 + 0.8 * p61)

        # P70 — Predicted impact energy normalized (0..1)
        p70 = 0.0
        if nearest:
            # E ~ 0.5 * m * v_rel^2 ; assume nominal mass m=4e5 kg (heavy train)
            v_rel = abs(v - nearest[3])
            E = 0.5 * 4e5 * (v_rel ** 2)  # Joules, v in m/s
            # normalize: treat 1e10 J as high-impact -> map E/1e10
            p70 = clamp01(E / 1e10)

        # P71 — Avoidance probability (higher -> easier to avoid => we invert to risk)
        # base on braking margin and sensor confidence (p76)
        # placeholder for sensor confidence below; use 0.8 default
        sensor_conf = 0.8
        p71 = clamp01(1.0 - (max(0.0, (1.0 - p64)) * 0.8 + (1.0 - sensor_conf) * 0.2))

        # P72 — Movement coherence (smoothness vs jitter)
        # inverse of jerk proxy; approximate from speed variations if available
        prev_speed = t.get("prev_speed", t.get("speed", 0.0))
        speed_var = abs(t.get("speed", 0.0) - prev_speed)
        p72 = clamp01(speed_var / 50.0)

        # P73 — Redundancy index (how many alternative edges available around current position)
        p73 = 0.0
        # if station graph supplied, compute degree of current node
        if stations:
            # find nearest station in path (use source or path[0])
            cur_node = t.get("path", [None])[0] or t.get("source")
            deg = 0
            for e in edges or []:
                if e["source"] == cur_node or e["target"] == cur_node:
                    deg += 1
            # higher degree => more alternatives => safer => invert for risk
            if deg > 0:
                p73 = clamp01(1.0 - (deg / 10.0))
            else:
                p73 = 1.0
        else:
            p73 = 0.5

        # P74 — Braking system load (proxy: speed * p66)
        p74 = clamp01(min(1.0, (v / (30.0)) * (0.5 + 0.5 * p66)))

        # P75 — Sensor/telemetry confidence (0..1, higher good -> invert for risk later)
        # If train object has telemetry_quality use it, else infer from missing fields
        tq = t.get("telemetry_quality", None)
        if tq is None:
            # infer: if lat/lon present and speed exists -> decent
            tq = 0.8 if ("lat" in t and "lon" in t and "speed" in t) else 0.4
        p75 = clamp01(1.0 - tq)  # higher means lower confidence => worse

        # P76 — Communication latency risk (0..1) — if train has comm_latency use it
        comm_latency = t.get("comm_latency_ms", 200)
        # map 0..2000ms to 0..1 (higher = worse)
        p76 = clamp01(comm_latency / 2000.0)

        # P77 — Historical near-miss factor (if available)
        near_miss = t.get("near_miss_count", 0)
        p77 = clamp01(min(1.0, near_miss / 10.0))

        # P78 — Emergency braking availability index (0..1) higher=bad if unavailable)
        eb_avail = t.get("emergency_brake_ok", True)
        p78 = 0.0 if eb_avail else 1.0

        # P79 — Local control reaction probability (human/operator factor)
        # lower skill or fatigue increases risk. Use driver_fatigue if present (0..1 where 1=high fatigue)
        fatigue = t.get("driver_fatigue", 0.2)
        p79 = clamp01(fatigue)

        # P80 — Composite collision risk index (final)
        # weighted sum: proximity, TTC, braking margin, edge conflict, sensor issues, predicted impact
        p80_raw = (
            0.18 * p61 +
            0.15 * p63 +
            0.15 * p64 +
            0.12 * p66 +
            0.10 * p70 +
            0.10 * p75 +
            0.08 * p67 +
            0.07 * p76 +
            0.05 * p79
        )
        p80 = clamp01(p80_raw)

        # Put into result dict (p61..p80)
        results[tid] = {
            "p61": clamp01(p61),
            "p62": clamp01(p62),
            "p63": clamp01(p63),
            "p64": clamp01(p64),
            "p65": clamp01(p65),
            "p66": clamp01(p66),
            "p67": clamp01(p67),
            "p68": clamp01(p68),
            "p69": clamp01(p69),
            "p70": clamp01(p70),
            "p71": clamp01(p71),
            "p72": clamp01(p72),
            "p73": clamp01(p73),
            "p74": clamp01(p74),
            "p75": clamp01(p75),
            "p76": clamp01(p76),
            "p77": clamp01(p77),
            "p78": clamp01(p78),
            "p79": clamp01(p79),
            "p80": clamp01(p80)
        }

    return results
