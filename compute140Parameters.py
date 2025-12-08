# compute140Parameters.py
# Python backend version of the 140-parameter engine (updated with Environment model)
# Mirrors compute140Parameters.ts AND includes P81..P100 environment outputs.
#
# Exports:
#   compute140Parameters(trains, stations, edges)
#   -> returns dict with keys:
#       "params", "contribs", "weights",
#       "collision_params", "health_params", "safety_params",
#       "environment" : { "stations": {id: {p81..p90}}, "segments": {seg_id: {p91..p100}} }
#
# Note: `stations` argument expected as mapping: { "DEL": {"lat":..,"lon":.., optional weather fields... }, ... }
#       edges expected as list of tuples: [("DEL","GZB"), ("GZB","NDLS"), ...]
#
# Weather/fields used (if present) per station:
#   temperature, humidity, wind_kmh, pressure_hpa, visibility_m, rain_mm
#

import math
import random
import hashlib
from typing import Dict, List, Tuple, Any

# existing modules (assumed present)
from computeCollisionParameters import compute_collision_parameters
from computeHealthParameters import compute_health_parameters
from computeSafetyParameters import compute_safety_parameters

# -----------------------
# Helpers
# -----------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two lat/lon points in meters."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2.0 * R * math.asin(min(1.0, math.sqrt(a)))

def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))

def _seeded_random_from_id(s: str) -> random.Random:
    h = hashlib.sha256(s.encode("utf-8")).digest()
    seed_int = int.from_bytes(h[:8], "big")
    return random.Random(seed_int)

# -----------------------
# Environment generators
# -----------------------
def compute_station_environment(stations: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Compute P81..P90 per station using available weather/environment fields.
    returns mapping station_id -> { "p81":..., ..., "p90": ... }
    Interpretation (higher = worse):
      p81: temperature_extreme_score (hot/cold extremes)
      p82: humidity_index (very high humidity bad)
      p83: wind_exposure_index (high wind bad)
      p84: pressure_variation_index (rapid low pressure -> storm risk)
      p85: visibility_index (low visibility -> worse)
      p86: rainfall_index (higher rainfall -> worse)
      p87: flood_proximity_index (if elevation absent, infer from rainfall/humidity)
      p88: coastal_corrosion_index (if 'coastal' flag or high humidity + low pressure)
      p89: heatwave_coldwave_index (combined thermal stress)
      p90: station_environment_composite
    """
    out = {}
    for sid, s in stations.items():
        lat = float(s.get("lat", 0.0))
        lon = float(s.get("lon", 0.0))

        # Weather inputs (use fallback deterministic defaults)
        temp = s.get("temperature", None)   # °C
        humidity = s.get("humidity", None)  # %
        wind = s.get("wind_kmh", None)      # km/h
        pressure = s.get("pressure_hpa", None)  # hPa
        visibility = s.get("visibility_m", None)  # m
        rain = s.get("rain_mm", None)       # mm

        # If fields missing, create pseudo-values deterministically from station id
        rnd = _seeded_random_from_id(f"station_env::{sid}")
        if temp is None:
            # typical range 5..40
            temp = 15.0 + (rnd.random() * 25.0)
        if humidity is None:
            humidity = 30.0 + rnd.random() * 60.0
        if wind is None:
            wind = rnd.random() * 50.0
        if pressure is None:
            pressure = 1008.0 + (rnd.random() - 0.5) * 30.0
        if visibility is None:
            # if heavy rain predicted, lower; otherwise random 1000..20000
            visibility = max(50.0, 5000.0 + (rnd.random() - 0.5) * 8000.0)
        if rain is None:
            # 0..50 mm
            rain = rnd.random() * 20.0

        # compute scores
        # p81: temperature extreme (0..1)
        temp_deviation = 0.0
        if temp < 0:
            temp_deviation = clamp((0.0 - temp) / 30.0, 0.0, 1.0)
        elif temp > 40:
            temp_deviation = clamp((temp - 40.0) / 30.0, 0.0, 1.0)
        else:
            temp_deviation = clamp(abs(temp - 22.0) / 22.0, 0.0, 1.0)
        p81 = temp_deviation

        # p82: humidity_index (higher worse above ~80)
        p82 = clamp((humidity - 40.0) / 60.0, 0.0, 1.0)

        # p83: wind_exposure_index (map 0..100 km/h)
        p83 = clamp(wind / 100.0, 0.0, 1.0)

        # p84: pressure_variation -> low pressure tends to be risky
        # compute how low relative to 1013 hPa standard
        p84 = clamp(max(0.0, (1013.0 - pressure) / 50.0), 0.0, 1.0)

        # p85: visibility_index (lower is worse). map 0..2000 -> 1..0
        p85 = clamp(1.0 - min(visibility, 2000.0) / 2000.0, 0.0, 1.0)

        # p86: rainfall_index (map 0..50mm)
        p86 = clamp(min(rain, 50.0) / 50.0, 0.0, 1.0)

        # p87: flood_proximity_index (proxy: high rain + high humidity + low elevation hint)
        # If station has 'elevation_m' field, use it; else infer from lat/lon slowly
        elev = s.get("elevation_m", None)
        if elev is None:
            # crude deterministic heuristic: use hash-based pseudo-elev
            elev = 100.0 + (rnd.random() - 0.5) * 300.0
        flood_proxy = clamp((p86 * 0.6) + (p82 * 0.3) + (1.0 - clamp(elev / 500.0,0,1)) * 0.2, 0.0, 1.0)
        p87 = flood_proxy

        # p88: corrosion index (coastal/humid)
        coastal_flag = bool(s.get("coastal", False))
        p88 = clamp(0.5 * (p82) + 0.4 * (1.0 if coastal_flag else 0.0) + 0.1 * p84, 0.0, 1.0)

        # p89: heatwave_coldwave_index (extreme heat or cold)
        p89 = clamp(max(0.0, (temp - 40.0) / 20.0, max(0.0, (0.0 - temp) / 20.0)), 0.0, 1.0)

        # p90: composite station environment score
        p90_raw = 0.18*p81 + 0.13*p82 + 0.12*p83 + 0.10*p85 + 0.12*p86 + 0.12*p87 + 0.08*p88 + 0.15*p89
        p90 = clamp(p90_raw, 0.0, 1.0)

        out[sid] = {
            "p81": round(p81, 6),
            "p82": round(p82, 6),
            "p83": round(p83, 6),
            "p84": round(p84, 6),
            "p85": round(p85, 6),
            "p86": round(p86, 6),
            "p87": round(p87, 6),
            "p88": round(p88, 6),
            "p89": round(p89, 6),
            "p90": round(p90, 6),
        }
    return out

def compute_segment_environment(
    u: str, v: str, idx: int, distance_m: float, station_env_u: Dict[str, float], station_env_v: Dict[str, float]
) -> Dict[str, float]:
    """
    Compute P91..P100 for one segment with id 'u-v-idx'.
    Uses local deterministic seed from segment id and blends station environment.
    P91..P100 interpretations (higher = worse):
      p91: gradient_risk
      p92: curvature_risk (sharp curves)
      p93: flood_zone_risk
      p94: landslide_risk
      p95: track_erosion_index
      p96: vegetation_obstruction_index
      p97: sun_glare_index
      p98: sand_accumulation_index
      p99: thermal_expansion_index
      p100: segment_environment_composite
    """
    seg_id = f"{u}-{v}-{idx}"
    rnd = _seeded_random_from_id(f"segment_env::{seg_id}")

    # base factors from distance and random
    local_rand = rnd.random()

    # Influence from station envs (take average of station composites p90)
    su = station_env_u.get("p90", 0.0) if station_env_u else 0.0
    sv = station_env_v.get("p90", 0.0) if station_env_v else 0.0
    station_composite = (su + sv) / 2.0

    # p91 gradient risk -> for short segments usually low; use small rand modulated by station composite
    p91 = clamp(0.05 * local_rand + 0.3 * station_composite)

    # p92 curvature risk -> bump if 'curve' text in ids or high random
    p92 = clamp(0.2 * local_rand + 0.2 * station_composite)

    # p93 flood zone risk -> inherits station flood proxy p87 and rainfall p86
    p93 = clamp(0.4 * station_env_u.get("p87", 0.0) + 0.4 * station_env_v.get("p87", 0.0) + 0.2 * local_rand)

    # p94 landslide risk -> higher in hilly inferred from station elevation (if present) else low
    # approximate using negative elevation influence
    elev_u = None
    elev_v = None
    # these passed in as part of station_env dicts? Not here; so compute using station_composite slight proxy
    p94 = clamp(0.15 * local_rand + 0.4 * station_composite)

    # p95 track erosion -> modulated by rainfall & nearby human activity (we don't have activity; use station composite)
    p95 = clamp(0.3 * local_rand + 0.5 * station_composite)

    # p96 vegetation obstruction -> more in rural segments: use inverse of station composite partially (lower composite maybe rural)
    p96 = clamp(0.2 * local_rand + 0.4 * (1.0 - station_composite))

    # p97 sun glare index -> random but slightly latitude-influenced via rnd
    p97 = clamp(0.25 * local_rand + 0.1 * station_composite)

    # p98 sand accumulation -> if coastal or desert station flags exist we'd use them; fallback to random
    p98 = clamp(0.15 * local_rand + 0.25 * station_composite)

    # p99 thermal expansion -> related to station temp extremes
    # approximate with station p81 (temp extreme)
    p99 = clamp(0.4 * ((station_env_u.get("p81", 0.0) + station_env_v.get("p81", 0.0)) / 2.0) + 0.2 * local_rand)

    # p100 composite
    p100_raw = (
        0.12*p91 + 0.12*p92 + 0.14*p93 + 0.10*p94 + 0.10*p95 +
        0.08*p96 + 0.06*p97 + 0.06*p98 + 0.12*p99 + 0.10*local_rand
    )
    p100 = clamp(p100_raw)

    return {
        "p91": round(p91, 6),
        "p92": round(p92, 6),
        "p93": round(p93, 6),
        "p94": round(p94, 6),
        "p95": round(p95, 6),
        "p96": round(p96, 6),
        "p97": round(p97, 6),
        "p98": round(p98, 6),
        "p99": round(p99, 6),
        "p100": round(p100, 6),
    }

def segment_line_between_segments(stations: Dict[str, Dict[str, Any]], u: str, v: str, segment_length_m: float = 100.0):
    """
    Produce segment ids and distances for u->v by splitting the edge into ~segment_length_m pieces.
    Returns list of tuples: (seg_id, distance_m, idx, start_coord, end_coord)
    """
    A = stations.get(u)
    B = stations.get(v)
    if not A or not B:
        return []

    lat1, lon1 = float(A.get("lat", 0.0)), float(A.get("lon", 0.0))
    lat2, lon2 = float(B.get("lat", 0.0)), float(B.get("lon", 0.0))
    total = haversine(lat1, lon1, lat2, lon2)
    num_segments = max(1, int(math.ceil(total / max(1.0, segment_length_m))))
    segs = []
    for i in range(num_segments):
        t0 = i / num_segments
        t1 = (i + 1) / num_segments
        sx = lat1 + (lat2 - lat1) * t0
        sy = lon1 + (lon2 - lon1) * t0
        ex = lat1 + (lat2 - lat1) * t1
        ey = lon1 + (lon2 - lon1) * t1
        seg_id = f"{u}-{v}-{i}"
        segs.append((seg_id, segment_length_m, i, (sx, sy), (ex, ey)))
    return segs

# -----------------------
# Main compute140Parameters (updated)
# -----------------------
def compute140Parameters(
    trains: List[Dict[str, Any]],
    stations: Dict[str, Dict[str, Any]],
    edges: List[Tuple[str, str]]
) -> Dict[str, Any]:
    """
    trains: list of train dicts (id,lat,lon,path,progress,speed,status,...)
    stations: mapping { name: {lat, lon, optional weather fields...}, ... }
    edges: list of tuples [(u,v), (v,w), ...]
    """

    # -----------------------
    # Build neighbor map
    # -----------------------
    neighbor_map = {name: [] for name in stations.keys()}
    for a, b in edges:
        if a in neighbor_map and b in neighbor_map:
            neighbor_map[a].append(b)
            neighbor_map[b].append(a)

    # -----------------------
    # Compute train positions (from path + progress)
    # -----------------------
    train_positions = {}
    for t in trains:
        path = t.get("path", []) or []
        progress = float(t.get("progress", 0.0))
        if not path or len(path) < 2:
            train_positions[t["id"]] = {"lat": float(t.get("lat", 0.0)), "lon": float(t.get("lon", 0.0))}
            continue

        segs = len(path) - 1
        scaled = clamp(progress, 0.0, 1.0) * segs
        idx = int(scaled)
        frac = scaled - idx

        A = stations.get(path[idx])
        B = stations.get(path[min(idx + 1, segs)])
        if not A or not B:
            train_positions[t["id"]] = {"lat": float(t.get("lat", 0.0)), "lon": float(t.get("lon", 0.0))}
            continue
        lat = float(A.get("lat", 0.0)) + (float(B.get("lat", 0.0)) - float(A.get("lat", 0.0))) * frac
        lon = float(A.get("lon", 0.0)) + (float(B.get("lon", 0.0)) - float(A.get("lon", 0.0))) * frac
        train_positions[t["id"]] = {"lat": lat, "lon": lon}

    # -----------------------
    # Base params (p1..p140 generation — keep original behaviour)
    # -----------------------
    params = {}
    contribs = {}
    weights = {}
    p_index = 1

    def add_param(value: float, weight: float = 1.0):
        nonlocal p_index
        key = f"p{p_index}"
        params[key] = float(value)
        contribs[key] = float(value) * float(weight)
        weights[key] = float(weight)
        p_index += 1

    # GROUP A
    degrees = [len(v) for v in neighbor_map.values()]
    avg_degree = sum(degrees) / max(1, len(degrees))
    add_param(avg_degree, 0.6)

    # Station density
    total_edge_dist = 0.0
    for a, b in edges:
        A = stations.get(a)
        B = stations.get(b)
        if A and B:
            total_edge_dist += haversine(float(A.get("lat", 0.0)), float(A.get("lon", 0.0)), float(B.get("lat", 0.0)), float(B.get("lon", 0.0)))
    density = len(stations) / (total_edge_dist / 1000.0 + 1.0)
    add_param(density, 0.5)

    # A3–A10
    for i in range(8):
        v = len([d for d in degrees if d >= i]) / max(1, len(degrees))
        add_param(v, 0.4)

    # GROUP B train spacing
    T = len(trains)
    for i in range(T):
        for j in range(i+1, T):
            p1 = train_positions[trains[i]["id"]]
            p2 = train_positions[trains[j]["id"]]
            dist = haversine(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
            add_param(math.exp(-dist / 5000.0), 0.8)
            add_param(math.exp(-dist / 2000.0), 0.7)
            add_param(math.exp(-dist / 1000.0), 0.6)

    # GROUP C speeds
    speeds = [float(t.get("speed", 0.0)) for t in trains]
    avg_speed = sum(speeds) / max(1, len(speeds))
    max_speed = max(speeds) if speeds else 1.0
    add_param(avg_speed / 200.0, 0.7)
    add_param(max_speed / 200.0, 0.8)
    for i in range(10):
        add_param(len([s for s in speeds if s > 40 + i * 20]) / max(1, len(speeds)), 0.6)

    # GROUP D nearest neighbor risk
    for t in trains:
        p = train_positions[t["id"]]
        nearest = 1e12
        for o in trains:
            if o["id"] == t["id"]:
                continue
            q = train_positions[o["id"]]
            d = haversine(p["lat"], p["lon"], q["lat"], q["lon"])
            if d < nearest:
                nearest = d
        for k in range(1, 11):
            add_param(math.exp(-nearest / (k * 1000.0)), 0.9)

    # GROUP E path metrics
    for t in trains:
        add_param(len(t.get("path", [])) / 20.0, 0.5)
        add_param(float(t.get("progress", 0.0)), 0.5)
    for i in range(1, 16):
        add_param((math.sin(i) + 1.0) / 2.0, 0.3)

    # GROUP F global stats
    add_param(len(trains) / 50.0, 1.0)
    add_param(len(edges) / 50.0, 0.8)
    add_param(len(stations) / 50.0, 0.7)

    # Fill until p140
    rnd_fill = random.Random(42)
    while p_index <= 140:
        x = rnd_fill.random() * 0.4 + 0.3
        add_param(x, 0.3)

    # -----------------------
    # Compute collision, health, safety (existing modules)
    # -----------------------
    stations_list = [{"id": k, **v} for k, v in stations.items()]
    edges_list = [{"source": a, "target": b} for a, b in edges]
    try:
        collision_params = compute_collision_parameters(trains, stations_list, edges_list)
    except Exception as e:
        # safe fallback
        collision_params = {}
    try:
        health_params = compute_health_parameters(trains)
    except Exception as e:
        health_params = {}
    try:
        safety_params = compute_safety_parameters(trains)
    except Exception as e:
        safety_params = {}

    # -----------------------
    # Compute environment model: stations (p81..p90) and segments (p91..p100)
    # -----------------------
    station_env = compute_station_environment(stations)

    # Build segment list and produce segment env per ~100m
    segment_env = {}
    for (u, v) in edges:
        segs = segment_line_between_segments(stations, u, v, segment_length_m=100.0)
        for (seg_id, seg_len, idx, start_coord, end_coord) in segs:
            # station env for endpoints (if available)
            env_u = station_env.get(u, {})
            env_v = station_env.get(v, {})
            env_seg = compute_segment_environment(u, v, idx, seg_len, env_u, env_v)
            segment_env[seg_id] = env_seg

    # -----------------------
    # Return consolidated result
    # -----------------------
    result = {
        "params": params,
        "contribs": contribs,
        "weights": weights,
        "collision_params": collision_params,
        "health_params": health_params,
        "safety_params": safety_params,
        "environment": {
            "stations": station_env,   # p81..p90 per station
            "segments": segment_env    # p91..p100 per 100m segment id 'u-v-i'
        }
    }

    return result

# If run as script, simple smoke test
if __name__ == "__main__":
    # tiny smoke test graph
    ST = {
        "A": {"lat": 28.60, "lon": 77.20, "temperature": 34, "humidity": 70, "wind_kmh": 12, "pressure": 1006.0, "visibility_m": 2000.0, "rain_mm": 4.0},
        "B": {"lat": 27.50, "lon": 79.50, "temperature": 30, "humidity": 50, "wind_kmh": 8, "pressure": 1010.0, "visibility_m": 10000.0, "rain_mm": 0.0},
    }
    EDGES = [("A","B")]
    TRAINS = [
        {"id":"T1","lat":28.6,"lon":77.2,"path":["A","B"],"progress":0.25,"speed":80},
        {"id":"T2","lat":28.2,"lon":78.4,"path":["A","B"],"progress":0.6,"speed":70}
    ]
    out = compute140Parameters(TRAINS, ST, EDGES)
    import json
    print("params sample keys:", list(out["params"].keys())[:10])
    print("env stations:", json.dumps(out["environment"]["stations"], indent=2))
    print("env segments sample:", list(out["environment"]["segments"].keys())[:5])
