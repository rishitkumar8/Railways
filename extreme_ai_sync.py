# extreme_ai_sync.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple, Any
import math
import heapq
import random
import logging
import threading
import time

# IMPORT YOUR 140-PARAM ENGINE (must return (params, contributions, weights))
from compute140Parameters import compute140Parameters

# -----------------------------
# safe wrapper around compute140Parameters
# -----------------------------
def compute140_safe(trains, stations, edges):
    """
    Calls the user's compute140Parameters and normalizes the output to:
      (params_map: dict, contribs_map: dict, weights_map: dict)
    The user engine may return different shapes; this wrapper accepts:
      - (params, contribs, weights)
      - {"params":..., "contribs":..., "weights":...}
      - single dict of params
    Always returns three dicts (empty dicts on failure).
    """
    try:
        out = compute140Parameters(trains, stations, edges)
        # common case: tuple/list of three
        if isinstance(out, (list, tuple)):
            if len(out) == 3:
                params, contribs, weights = out
            elif len(out) == 2:
                params, contribs = out
                weights = {k: 1.0 for k in (params.keys() if isinstance(params, dict) else [])}
            else:
                params = out[0] if len(out) > 0 else {}
                contribs = out[1] if len(out) > 1 else {}
                weights = out[2] if len(out) > 2 else {}
        elif isinstance(out, dict):
            params = out.get("params", out)
            contribs = out.get("contribs", out.get("contributions", {}))
            weights = out.get("weights", out.get("param_weights", {}))
        else:
            # unknown shape — try to coerce
            params = {}
            contribs = {}
            weights = {}
        # normalize to dicts
        params = params or {}
        contribs = contribs or {}
        weights = weights or {}
        if not isinstance(params, dict): params = dict(params)
        if not isinstance(contribs, dict): contribs = dict(contribs)
        if not isinstance(weights, dict): weights = dict(weights)
        return params, contribs, weights
    except Exception as e:
        logger.exception("compute140_safe: compute140Parameters crashed: %s", e)
        # return empty safe defaults so decision logic continues
        return {}, {}, {}

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("extreme_ai_sync")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CONFIG
SAFE_DISTANCE = 1000.0
LOOKAHEAD = 30.0
RISK_THRESHOLD = 0.55
MONTE_SIMS = 100

# In-memory latest graph (auto-synced by incoming /decide payloads)
current_graph: Dict[str, Any] = {
    "stations": {},  # name -> { lat, lon }
    "edges": []      # list of [u,v]
}
current_trains: List[Dict[str, Any]] = []  # last-known trains (list of dicts)

# Spawn engine config
spawn_enabled = False
spawn_interval = 10  # seconds
max_trains = 100
spawned_trains: List[Dict[str, Any]] = []

# Utility functions
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2.0)**2
    return 2.0 * R * math.asin(math.sqrt(a))

def safe_station_coord(stations: Dict[str, Dict[str,float]], name: str, fallback: Tuple[float,float]=(0.0,0.0)):
    """Return (lat, lon) for station name or fallback if missing."""
    s = stations.get(name)
    if s and isinstance(s, dict) and "lat" in s and "lon" in s:
        try:
            return float(s["lat"]), float(s["lon"])
        except Exception:
            return fallback
    return fallback

def edge_length_m(stations: Dict[str, Dict[str,float]], u: str, v: str) -> float:
    a = safe_station_coord(stations, u)
    b = safe_station_coord(stations, v)
    return haversine(a[0], a[1], b[0], b[1])

def dijkstra(stations: Dict[str, Dict[str,float]], edges: List[List[str]], start: str, goal: str, blocked: set = None):
    if blocked is None:
        blocked = set()
    # Ensure nodes exist in adjacency (even if they have no coords)
    adj: Dict[str, List[Tuple[str,float]]] = {}
    nodes = set()
    for s in stations.keys():
        nodes.add(s)
        adj[s] = []
    # also include nodes that appear in edges but not in stations
    for u,v in edges:
        nodes.add(u); nodes.add(v)
        if u not in adj: adj[u] = []
        if v not in adj: adj[v] = []
    for u,v in edges:
        if (u,v) in blocked or (v,u) in blocked:
            continue
        dist = edge_length_m(stations, u, v)
        adj[u].append((v, dist))
        adj[v].append((u, dist))
    if start not in adj or goal not in adj:
        return None
    pq = [(0.0, start, [start])]
    seen: Dict[str,float] = {}
    while pq:
        d, node, path = heapq.heappop(pq)
        if node == goal:
            return path
        if node in seen and seen[node] <= d:
            continue
        seen[node] = d
        for nxt, w in adj.get(node, []):
            nd = d + w
            if nxt in seen and seen[nxt] <= nd: continue
            heapq.heappush(pq, (nd, nxt, path + [nxt]))
    return None

def predict_future_pos(train: Dict[str,Any], stations: Dict[str, Dict[str,float]], seconds_ahead: float):
    """Linear along path prediction that tolerates missing stations.
       If a path node is missing from stations, fallback to last known lat/lon on the train object."""
    try:
        if not train.get("path") or len(train["path"]) < 2:
            return float(train.get("lat",0.0)), float(train.get("lon",0.0))
        path = train["path"]
        speed_ms = max(float(train.get("speed",0.1)), 0.1) * 1000.0 / 3600.0
        remaining = speed_ms * float(seconds_ahead)
        segments = len(path) - 1
        progress = float(train.get("progress", 0.0))
        scaled = min(max(progress, 0.0), 1.0) * segments
        idx = int(min(int(scaled), segments-1))
        frac = scaled - idx

        def station_coord(i):
            name = path[i]
            return safe_station_coord(stations, name, fallback=(float(train.get("lat",0.0)), float(train.get("lon",0.0))))

        cur_lat, cur_lon = station_coord(idx)
        nlat, nlon = station_coord(idx+1)
        # interpolate
        cur_lat = cur_lat + (nlat - cur_lat) * frac
        cur_lon = cur_lon + (nlon - cur_lon) * frac

        edge_idx = idx
        edge_frac = frac
        while remaining > 0 and edge_idx < segments:
            u = path[edge_idx]
            v = path[edge_idx+1]
            edge_len = edge_length_m(stations, u, v)
            rem_on_edge = edge_len * (1.0 - edge_frac)
            if remaining < rem_on_edge:
                ratio = (edge_frac * edge_len + remaining) / edge_len if edge_len > 0 else 0.0
                ua = station_coord(edge_idx)
                va = station_coord(edge_idx+1)
                new_lat = ua[0] + (va[0] - va[0]) * ratio
                new_lon = ua[1] + (va[1] - va[1]) * ratio
                return new_lat, new_lon
            remaining -= rem_on_edge
            edge_idx += 1
            edge_frac = 0.0
        last = station_coord(len(path)-1)
        return last[0], last[1]
    except Exception as e:
        # fallback
        logger.debug("predict_future_pos fallback: %s", e)
        return float(train.get("lat",0.0)), float(train.get("lon",0.0))

def braking_distance_m(train: Dict[str,Any], adhesion_coeff=0.25, decel_override=None):
    v = max(float(train.get("speed", 0.1)), 0.1) * 1000.0 / 3600.0
    if decel_override:
        a = decel_override
    else:
        a = max(9.81 * max(adhesion_coeff, 0.05), 0.1)
    if a <= 0:
        return 1e9
    return (v*v) / (2.0 * a)

# Monte Carlo helper (kept lightweight)
def monte_carlo_risk_eval(base_score, uncertainty_sd=0.12, sims=MONTE_SIMS):
    count = 0
    for _ in range(sims):
        sample = random.gauss(base_score, uncertainty_sd)
        if sample > RISK_THRESHOLD:
            count += 1
    return count / max(1, sims)

# Pydantic models for incoming payloads
class TrainModel(BaseModel):
    id: str
    name: Optional[str]
    lat: float
    lon: float
    source: str
    destination: str
    path: List[str]
    progress: float = 0.0
    speed: float = 100.0
    priority: int = 1
    status: Optional[str] = "MOVING"

class GraphModel(BaseModel):
    stations: Dict[str, Dict[str, float]]
    edges: List[List[str]]

class InputModel(BaseModel):
    trains: List[TrainModel]
    graph: GraphModel

class ApplyModel(BaseModel):
    train_id: str
    new_path: List[str]

# ===========================
# Core /decide endpoint (AUTO-SYNC)
# ===========================
@app.post("/decide")
def decide(data: InputModel):
    global current_graph, current_trains
    # 1) Auto-sync the graph & trains
    try:
        # normalize stations: ensure values are floats
        stations = {k: {"lat": float(v.get("lat",0.0)), "lon": float(v.get("lon",0.0))} for k,v in (data.graph.stations or {}).items()}
        edges = [list(e) for e in (data.graph.edges or [])]
        trains = [t.dict() for t in data.trains]
    except Exception as e:
        logger.exception("Invalid payload structure")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    # persist the latest view (so /spawn and stress endpoints can use it)
    current_graph = {"stations": stations, "edges": edges}
    current_trains = trains

    try:
        params_map, contribs_map, weights_map = compute140_safe(trains, stations, edges)
    except Exception as e:
        # Should not happen due to wrapper, but keep safe guard
        logger.exception("Unexpected error when computing params: %s", e)
        raise HTTPException(status_code=500, detail="Parameter engine failure")

    # pairwise evaluation
    highest = {"score": 0.0, "pair": None, "details": None}
    n = len(trains)
    for i in range(n):
        for j in range(i+1, n):
            A = trains[i]; B = trains[j]
            try:
                cur_dist = haversine(float(A["lat"]), float(A["lon"]), float(B["lat"]), float(B["lon"]))
                a_lat, a_lon = predict_future_pos(A, stations, LOOKAHEAD)
                b_lat, b_lon = predict_future_pos(B, stations, LOOKAHEAD)
                fut_dist = haversine(a_lat, a_lon, b_lat, b_lon)
                vA = max(float(A.get("speed",0.1)), 0.1) * 1000.0/3600.0
                vB = max(float(B.get("speed",0.1)), 0.1) * 1000.0/3600.0
                rel = abs(vA - vB) + 1e-6
                ttc = fut_dist / rel if rel > 0 else float("inf")
                brakeA = braking_distance_m(A)
                brakeB = braking_distance_m(B)

                proximity_score = max(0.0, 1.0 - (fut_dist / (SAFE_DISTANCE * 2.0)))
                ttc_score = max(0.0, 1.0 - min(ttc / (LOOKAHEAD * 2.0), 1.0))
                braking_score = max(0.0, 1.0 - (min(brakeA, brakeB) / (SAFE_DISTANCE * 2.0)))

                base_score = 0.33*proximity_score + 0.33*ttc_score + 0.34*braking_score

                total_w = sum(weights_map.values()) if weights_map else 1.0
                paramRisk = sum(contribs_map.values()) / total_w if total_w > 0 else 0.0

                final = max(0.0, min(1.0, 0.6*base_score + 0.4*paramRisk))

                # Monte Carlo blend
                mc = monte_carlo_risk_eval(final, uncertainty_sd=0.12)
                blended = 0.8*final + 0.2*mc
                blended = max(0.0, min(1.0, blended))

                details = {
                    "pair": (A["id"], B["id"]),
                    "cur_dist_m": cur_dist,
                    "future_dist_m": fut_dist,
                    "ttc_s": ttc,
                    "brake_A_m": brakeA,
                    "brake_B_m": brakeB,
                    "proximity_score": proximity_score,
                    "ttc_score": ttc_score,
                    "braking_score": braking_score,
                    "paramRisk": paramRisk,
                    "base_score": base_score,
                    "mc_prob": mc,
                    "final_score": blended
                }

                if blended > highest["score"]:
                    highest = {"score": blended, "pair": (A,B), "details": details}
            except Exception as e:
                logger.debug("pairwise eval error for %s-%s: %s", A.get("id"), B.get("id"), e)
                continue

    # Decision logic
    if highest["score"] >= RISK_THRESHOLD and highest["pair"]:
        A, B = highest["pair"]
        # pick lower priority to reroute/stop
        try:
            pa = int(A.get("priority",1))
            pb = int(B.get("priority",1))
        except Exception:
            pa, pb = 1, 1
        low = A if pa <= pb else B

        # compute current edge index safely
        idx = None
        if low.get("path") and len(low["path"]) >= 2:
            segs = len(low["path"])-1
            try:
                idx = int(min(max(math.floor(float(low.get("progress",0.0)) * segs), 0), segs-1))
            except Exception:
                idx = 0
        blocked_edge = None
        if idx is not None:
            u = low["path"][idx]
            v = low["path"][idx+1] if idx+1 < len(low["path"]) else None
            if v:
                blocked_edge = (u, v)

        # attempt reroute using latest graph (block the edge if found)
        blocked_set = set()
        if blocked_edge:
            blocked_set.add(tuple(blocked_edge))
        try:
            new_path = dijkstra(stations, edges, low["path"][idx] if idx is not None else low.get("source", low.get("path",[None])[0]), low.get("destination"), blocked=blocked_set)
        except Exception as e:
            logger.debug("dijkstra reroute error: %s", e)
            new_path = None

        reason = f"Predicted collision risk {highest['score']:.3f} >= {RISK_THRESHOLD}"
        response = {
            "action": "REQUEST_CONFIRMATION" if new_path else "STOP_BOTH",
            "train_id": low.get("id"),
            "suggested_path": new_path,
            "blocked_edge": blocked_edge,
            "reason": reason,
            "details": highest,
            "params": params_map,
            "param_contributions": contribs_map,
            "param_weights": weights_map
        }
        # add a log entry
        logger.warning("Decision: %s - train %s - score %.3f", response["action"], low.get("id"), highest["score"])
        return response

    # No high risk
    return {
        "action": "NORMAL",
        "reason": "All clear",
        "score": highest["score"],
        "params": params_map,
        "param_contributions": contribs_map,
        "param_weights": weights_map
    }

# Apply reroute (unchanged)
@app.post("/apply_reroute")
def apply_reroute(m: ApplyModel):
    # This endpoint is a stateless acknowledgement — frontend should update store.
    logger.info("apply_reroute called for: %s -> %s", m.train_id, m.new_path)
    return {"status": "ok", "train_id": m.train_id, "new_path": m.new_path}

@app.get("/health")
def health():
    # run a tiny self-check of compute engine with current_graph + up to 2 trains
    try:
        g = current_graph if current_graph.get("stations") else _default_graph()
        sample_trains = generate_stress_trains(2, chaos=False, graph=g)
        p,c,w = compute140_safe(sample_trains, g.get("stations",{}), g.get("edges",[]))
        return {"status": "running", "params": 140, "graph_nodes": len(current_graph.get("stations",{})), "graph_edges": len(current_graph.get("edges",[])), "sample_params_count": len(p)}
    except Exception as e:
        logger.exception("health check failed: %s", e)
        raise HTTPException(status_code=500, detail="health check failed")

# ---------------------------#
# Stress test endpoints that use current_graph when available
# ---------------------------#
def _default_graph():
    # fallback small graph if nothing synced yet (A-F)
    return {
        "stations": {
            "A":{"lat":28.60,"lon":77.20},
            "B":{"lat":28.00,"lon":78.00},
            "C":{"lat":26.90,"lon":80.90},
            "D":{"lat":27.50,"lon":79.50},
            "E":{"lat":27.20,"lon":78.80},
            "F":{"lat":26.50,"lon":79.90}
        },
        "edges": [["A","C"],["A","B"],["B","D"],["D","C"],["B","E"],["E","F"],["F","C"]]
    }

def generate_stress_trains(count:int, chaos:bool=False, graph=None):
    g = graph or current_graph or _default_graph()
    stations = list(g.get("stations",{}).keys())
    if not stations:
        stations = ["A","B","C","D","E","F"]
    trains=[]
    for i in range(count):
        s = random.choice(stations)
        d = random.choice(stations)
        while d == s:
            d = random.choice(stations)
        speed = random.randint(60,130)
        if chaos:
            speed += random.randint(-30,30)
        progress = random.random()*0.9
        lat, lon = safe_station_coord(g.get("stations",{}), s, fallback=(0.0,0.0))
        # simple linear interp to destination
        dlat, dlon = safe_station_coord(g.get("stations",{}), d, fallback=(lat,lon))
        lat = lat + (dlat - lat) * progress
        lon = lon + (dlon - lon) * progress
        trains.append({
            "id": f"ST{i+1}",
            "name": f"Stress-{i+1}",
            "source": s,
            "destination": d,
            "path": [s,d],
            "progress": progress,
            "speed": speed,
            "priority": random.randint(1,3),
            "status": "MOVING",
            "lat": lat,
            "lon": lon
        })
    return trains

@app.get("/stress_test_50")
def stress_test_50():
    graph = current_graph if current_graph.get("stations") else _default_graph()
    trains = generate_stress_trains(50, chaos=False, graph=graph)
    return {"trains": trains, "graph": graph}

@app.get("/stress_test_100")
def stress_test_100():
    graph = current_graph if current_graph.get("stations") else _default_graph()
    trains = generate_stress_trains(100, chaos=True, graph=graph)
    return {"trains": trains, "graph": graph}

@app.post("/sync")
def sync_graph(data: GraphModel):
    global current_graph
    try:
        # normalize stations: ensure values are floats
        stations = {k: {"lat": float(v.get("lat",0.0)), "lon": float(v.get("lon",0.0))} for k,v in (data.stations or {}).items()}
        edges = [list(e) for e in (data.edges or [])]
        current_graph = {"stations": stations, "edges": edges}
        logger.info("Graph synced: %d stations, %d edges", len(stations), len(edges))
        return {"status": "synced", "stations_count": len(stations), "edges_count": len(edges)}
    except Exception as e:
        logger.exception("Sync failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Sync failed: {e}")

@app.get("/stress_test_50_payload")
def stress_test_50_payload():
    graph = current_graph if current_graph.get("stations") else _default_graph()
    trains = generate_stress_trains(50, chaos=False, graph=graph)
    # sample /decide payload
    sample_payload = {"trains": trains, "graph": graph}
    return {"stress_trains": trains, "graph": graph, "sample_decide_payload": sample_payload}

# ---------------------------#
# Spawn engine (daemon thread) — uses latest graph
# ---------------------------#
def spawn_worker():
    global spawned_trains, spawn_enabled
    idx = 0
    while True:
        if spawn_enabled and len(spawned_trains) < max_trains:
            # generate one train using current graph
            g = current_graph if current_graph.get("stations") else _default_graph()
            new = generate_stress_trains(1, chaos=True, graph=g)[0]
            spawned_trains.append(new)
            logger.info("Spawned train %s (total %d)", new["id"], len(spawned_trains))
        time.sleep(spawn_interval)

_spawn_thread = threading.Thread(target=spawn_worker, daemon=True)
_spawn_thread.start()

@app.post("/spawn/toggle")
def toggle_spawn(enabled: bool):
    global spawn_enabled
    spawn_enabled = bool(enabled)
    return {"spawn_enabled": spawn_enabled, "interval_seconds": spawn_interval, "max_trains": max_trains}

@app.get("/spawn/status")
def spawn_status():
    return {"enabled": spawn_enabled, "interval_seconds": spawn_interval, "max_trains": max_trains, "spawned_count": len(spawned_trains)}

@app.post("/spawn/config")
def spawn_config(interval: Optional[int] = None, max_trains_limit: Optional[int] = None):
    global spawn_interval, max_trains
    if interval is not None:
        spawn_interval = max(1, int(interval))
    if max_trains_limit is not None:
        max_trains = max(1, int(max_trains_limit))
    return {"interval_seconds": spawn_interval, "max_trains": max_trains}

@app.get("/spawn/trains")
def get_spawned():
    return {"trains": spawned_trains, "count": len(spawned_trains)}

@app.delete("/spawn/clear")
def clear_spawned():
    global spawned_trains
    c = len(spawned_trains)
    spawned_trains = []
    return {"cleared": c, "remaining": 0}

# ---------------------------#
# Basic in-memory logs
# ---------------------------#
logs_buffer = []
MAX_LOGS = 2000
def push_log(level:str, message:str, train_id:Optional[str]=None):
    logs_buffer.append({"ts": time.time(), "level": level.upper(), "msg": message, "train_id": train_id})
    if len(logs_buffer) > MAX_LOGS:
        logs_buffer.pop(0)

@app.get("/logs")
def get_logs(level: Optional[str]=None, train_id: Optional[str]=None, limit: int=200):
    logs = logs_buffer
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    if train_id:
        logs = [l for l in logs if l.get("train_id") == train_id]
    return {"logs": logs[-limit:], "total": len(logs)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
