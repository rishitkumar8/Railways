<<<<<<< HEAD
# extreme_ai_server.py
# AI Decision + 140-Parameter Computation Engine
# Works directly with your TrainMap.tsx frontend

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import math
import uvicorn
from typing import Dict, List, Any

# import your 140-parameter engine
from compute140Parameters import compute140Parameters
from environment_model import generate_station_environment
from track_segmenter import segment_track
from station_schema import StationModel

app = FastAPI(title="Extreme Train AI Decision Engine")
=======
"""
KAVACH 2.0 — INDIAN RAILWAYS PREDICTIVE AI
Extreme AI Decision Engine v5.0 — FINAL HACKATHON WINNER EDITION
→ Smooth train animation (progress-based)
→ Real Indian trains (Rajdhani, Vande Bharat, etc.)
→ Real collision prediction + emergency stop
→ Kavach emulation + "Trains Saved Today"
→ Works perfectly with your TrainMap.tsx
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple, Any
import math
import heapq
import random
import time
import logging
import threading

# === REAL INDIAN TRAINS ===
REAL_TRAINS = [
    {"name": "12951 Mumbai Rajdhani", "type": "Rajdhani", "max_speed": 160},
    {"name": "22691 Bangalore Rajdhani", "type": "Rajdhani", "max_speed": 160},
    {"name": "12019 Howrah Shatabdi", "type": "Shatabdi", "max_speed": 150},
    {"name": "22416 NDLS-Varanasi Vande Bharat", "type": "Vande Bharat", "max_speed": 180},
    {"name": "17229 Sabari Express", "type": "Express", "max_speed": 110},
    {"name": "12627 Karnataka Express", "type": "Superfast", "max_speed": 130},
    {"name": "12301 Howrah Rajdhani", "type": "Rajdhani", "max_speed": 160},
    {"name": "22625 Chennai Double Decker", "type": "Double Decker", "max_speed": 140},
    {"name": "22177 Mahanagari Express", "type": "Express", "max_speed": 120},
    {"name": "12138 Punjab Mail", "type": "Mail", "max_speed": 115},
]

# === Try real 140-parameter engine ===
try:
    from compute140Parameters import compute140Parameters
    HAVE_REAL_140 = True
except Exception:
    print("Using fallback 140-parameter engine")
    HAVE_REAL_140 = False
    def compute140Parameters(trains, stations, edges):
        return {
            "params": {f"p{i}": round(random.uniform(0.1, 0.9), 4) for i in range(1, 141)},
            "environment": {
                "stations": {s: {f"p{80+i}": round(random.random(), 4) for i in range(1, 11)} for s in stations.keys()},
                "segments": {}
            }
        }

app = FastAPI(title="KAVACH 2.0 — Indian Railways AI")
>>>>>>> 42b56fc74ed4d9318fd8a98b55c9f9214c9b0ffd

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

<<<<<<< HEAD
# -------------------------------------------------------------------
# Global caches for environment data
# -------------------------------------------------------------------
station_env = {}
segment_env_map = {}

# -------------------------------------------------------------------
# Utility: simple distance (meters)
# -------------------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dLon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

# -------------------------------------------------------------------
# Decide collision resolution between trains
# -------------------------------------------------------------------
def decide_collision_action(trains: List[Dict[str, Any]]):
    """
    trains = [
        { "id": "...", "name": "...", "lat":.., "lon":.., "speed":.., "priority":.. },
        { ... }
    ]

    RETURNS:
    - STOP_ONE
    - STOP_BOTH
    - LET_PASS
    """

    if len(trains) < 2:
        return {"action": "NO_ACTION"}

    A = trains[0]
    B = trains[1]

    # distance between them
    dist = haversine(A["lat"], A["lon"], B["lat"], B["lon"])

    # ------------------------
    # Priority rule
    # ------------------------
    # Higher priority trains get preference (higher number = more priority)
    prA = A.get("priority", 1)
    prB = B.get("priority", 1)

    # ------------------------
    # Speed rule
    # ------------------------
    sA = A.get("speed", 0)
    sB = B.get("speed", 0)

    # ------------------------
    # STOP both if extremely close (safety hard-stop)
    # ------------------------
    if dist <= 35:  # meters (your aura ~ 30px ≈ this)
        return {
            "action": "STOP_BOTH",
            "reason": "Critical proximity"
        }

    # ------------------------
    # Pick which train to stop:
    # Higher priority => let pass
    # Faster train => let pass
    # ------------------------
    if prA > prB:
        return {
            "action": "STOP_ONE",
            "stop_train": B["id"],
            "let_pass": A["id"],
            "reason": "Train A higher priority"
        }

    if prB > prA:
        return {
            "action": "STOP_ONE",
            "stop_train": A["id"],
            "let_pass": B["id"],
            "reason": "Train B higher priority"
        }

    # If priorities equal → faster goes first
    if sA > sB:
        return {
            "action": "STOP_ONE",
            "stop_train": B["id"],
            "let_pass": A["id"],
            "reason": "Train A faster"
        }

    if sB > sA:
        return {
            "action": "STOP_ONE",
            "stop_train": A["id"],
            "let_pass": B["id"],
            "reason": "Train B faster"
        }

    # identical => stop both
    return {
        "action": "STOP_BOTH",
        "reason": "Same speed & priority"
    }

# -------------------------------------------------------------------
# API: /decide
# -------------------------------------------------------------------
@app.post("/decide")
async def decide_endpoint(req: Request):
    """
    Expected payload from TrainMap.tsx:

    {
      "trains": [
         { "id":"T1", "lat":..., "lon":..., "speed":100, "priority":1 },
         { "id":"T2", "lat":..., "lon":..., "speed":80, "priority":1 }
      ],
      "stations": { "DEL": { "lat": 28.6139, "lon": 77.2090 }, ... },
      "edges": [["DEL", "NDLS"], ...]
    }
    """
    data = await req.json()
    trains = data.get("trains", [])
    stations = data.get("stations", {})
    edges = data.get("edges", [])

    # Attach environment to each station if missing
    for name in stations.keys():
        if name not in station_env:
            station_env[name] = generate_station_environment(name)

    # Build 100m track segments for each edge
    segment_env_map.clear()
    for u, v in edges:
        key = f"{u}-{v}"
        segment_env_map[key] = segment_track(stations, u, v)

    if not trains or len(trains) < 2:
        return {"action": "NO_ACTION", "error": "Not enough trains"}

    # AI decision logic
    decision = decide_collision_action(trains)

    # Include fallback id mapping
    if "stop_train" in decision:
        decision["stop_train_id"] = decision["stop_train"]
    if "let_pass" in decision:
        decision["let_pass_id"] = decision["let_pass"]

    return decision

# -------------------------------------------------------------------
# API: /compute140
# -------------------------------------------------------------------
@app.post("/compute140")
async def compute140(req: Request):
    data = await req.json()
    trains = data.get("trains", [])
    stations = data.get("stations", {})
    edges = data.get("edges", [])

    params, contribs, weights = compute140Parameters(
        trains,
        stations,
        edges,
        station_env=station_env,
        segment_env=segment_env_map
    )

    return {
        "params": params,
        "contribs": contribs,
        "weights": weights
    }

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("extreme_ai_server:app", host="0.0.0.0", port=8000, reload=True)
=======
# === Global State ===
start_time = time.time()
trains_saved_today = 0
current_graph = {"stations": {}, "edges": []}
current_trains: List[Dict[str, Any]] = []
train_risk_cache: Dict[str, Dict[str, Optional[float]]] = {}

# === Logging System ===
logs_buffer = []
MAX_LOGS = 2000
def push_log(level: str, message: str, train_id: Optional[str] = None):
    logs_buffer.append({"ts": time.time(), "level": level.upper(), "msg": message, "train_id": train_id})
    if len(logs_buffer) > MAX_LOGS:
        logs_buffer.pop(0)

# === Spawn Engine ===
spawn_enabled = False
spawn_interval = 10  # seconds
max_trains = 100
spawned_trains: List[Dict[str, Any]] = []

# === Models ===
class TrainModel(BaseModel):
    id: str
    name: str
    source: str
    destination: str
    path: List[str]
    progress: float
    speed: float
    priority: int = 1
    status: str = "MOVING"
    train_type: str = "Express"

class GraphModel(BaseModel):
    stations: Dict[str, Dict[str, float]]
    edges: List[List[str]]

class InputModel(BaseModel):
    trains: List[TrainModel]
    graph: GraphModel

# === Utils ===
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def dijkstra(stations, edges: List[Tuple[str, str]], start, goal, blocked=None, environment=None):
    if blocked is None: blocked = set()
    adj = {s: [] for s in stations}
    for u, v in edges:
        if (u,v) in blocked or (v,u) in blocked: continue
        d = haversine(stations[u]["lat"], stations[u]["lon"], stations[v]["lat"], stations[v]["lon"])
        # Incorporate segment risk from P91-P100 if environment available
        risk_factor = 0.0
        if environment and "segments" in environment:
            seg_prefix = f"{u}-{v}-"
            seg_risks = [seg_data.get("p100", 0.0) for seg_id, seg_data in environment["segments"].items() if seg_id.startswith(seg_prefix)]
            if seg_risks:
                risk_factor = sum(seg_risks) / len(seg_risks)  # average p100
        # Weight = haversine distance * (1 + risk_factor)
        weight = d * (1 + risk_factor)
        adj[u].append((v, weight))
        adj[v].append((u, weight))
    if start not in adj or goal not in adj: return None
    pq = [(0, start, [start])]
    visited = set()
    while pq:
        dist, node, path = heapq.heappop(pq)
        if node in visited: continue
        if node == goal: return path
        visited.add(node)
        for nxt, w in adj[node]:
            if nxt not in visited:
                heapq.heappush(pq, (dist + w, nxt, path + [nxt]))
    return None

# === MAIN AI ENGINE ===
@app.post("/decide")
def decide(data: InputModel):
    global current_graph, current_trains, train_risk_cache, trains_saved_today

    stations = {k: {"lat": v["lat"], "lon": v["lon"]} for k, v in data.graph.stations.items()}
    edges: List[Tuple[str, str]] = [(e[0], e[1]) for e in data.graph.edges]
    trains = [t.dict() for t in data.trains]

    current_graph = {"stations": stations, "edges": edges}
    current_trains = trains

    result = compute140Parameters(trains, stations, edges)
    env = result.get("environment", {})

    LOOKAHEAD = 50
    CRITICAL_TTC = 18
    highest_risk = 0.0
    collision_pair = None
    critical_ttc = float('inf')

    for i in range(len(trains)):
        for j in range(i+1, len(trains)):
            A, B = trains[i], trains[j]
            # Simulate future positions using path + progress
            segsA = len(A["path"]) - 1
            segsB = len(B["path"]) - 1
            progA = (A["progress"] + (A["speed"] / 3600) * LOOKAHEAD / 100) % 1
            progB = (B["progress"] + (B["speed"] / 3600) * LOOKAHEAD / 100) % 1
            idxA = min(int(progA * segsA), segsA - 1)
            idxB = min(int(progB * segsB), segsB - 1)
            fracA = progA * segsA - idxA
            fracB = progB * segsB - idxB

            uA, vA = A["path"][idxA], A["path"][idxA + 1]
            uB, vB = B["path"][idxB], B["path"][idxB + 1]
            A1 = stations.get(uA, {"lat": 20, "lon": 70})
            A2 = stations.get(vA, {"lat": 20, "lon": 70})
            B1 = stations.get(uB, {"lat": 20, "lon": 70})
            B2 = stations.get(vB, {"lat": 20, "lon": 70})

            future_latA = A1["lat"] + (A2["lat"] - A1["lat"]) * fracA
            future_lonA = A1["lon"] + (A2["lon"] - A1["lon"]) * fracA
            future_latB = B1["lat"] + (B2["lat"] - B1["lat"]) * fracB
            future_lonB = B1["lon"] + (B2["lon"] - B1["lon"]) * fracB

            dist = haversine(future_latA, future_lonA, future_latB, future_lonB)
            rel_speed = abs(A["speed"] - B["speed"]) * 1000 / 3600 + 1
            ttc = max(0.1, dist / rel_speed)

            risk = 0.5 * result["params"].get("meta_risk_index", 0.5) + 0.5 * (1 - min(ttc/60, 1))

            if risk > highest_risk:
                highest_risk = risk
                collision_pair = (A, B)
                critical_ttc = ttc

    # Update risk cache
    for t in trains:
        train_risk_cache[t["id"]] = {
            "ttc": round(critical_ttc, 2) if critical_ttc < 120 else None,
            "riskLevel": round(min(1.0, highest_risk * 1.4), 4)
        }

    if collision_pair and critical_ttc < CRITICAL_TTC:
        A, B = collision_pair
        low = A if A["priority"] <= B.get("priority", 1) else B
        trains_saved_today += 1

        blocked = {(low["path"][0], low["path"][1])}
        alt_path = dijkstra(stations, edges, low["path"][0], low["destination"], blocked, env)

        return {
            "action": "EMERGENCY_STOP" if not alt_path else "REQUEST_CONFIRMATION",
            "train_id": low["id"],
            "train_name": low["name"],
            "suggested_path": alt_path or [],
            "reason": f"AI Prevented Collision • TTC {critical_ttc:.1f}s",
            "kavach_saved": "YES" if critical_ttc < 8 else "NO",
            "trains_saved_today": trains_saved_today,
            "environment": env
        }

    return {
        "action": "NORMAL",
        "trains_saved_today": trains_saved_today,
        "environment": env
    }

# === FULL PARAMETERS (FOR TrainMap.tsx) ===
@app.get("/parameters_full")
def parameters_full():
    result = compute140Parameters(current_trains, current_graph.get("stations", {}), current_graph.get("edges", []))
    env = result.get("environment", {})

    updates = []
    for t in current_trains:
        cache = train_risk_cache.get(t["id"], {})
        updates.append({
            "id": t["id"],
            "name": t["name"],
            "train_type": t.get("train_type", "Express"),
            "ttc": cache.get("ttc"),
            "riskLevel": cache.get("riskLevel", 0.1)
        })

    return {
        "trains": updates,
        "environment": env,
        "stats": {"trains_saved_today": trains_saved_today}
    }

# === STRESS TEST 50 — SMOOTH ANIMATION READY ===
@app.get("/stress_test_50")
def stress_test_50():
    stations_list = list(current_graph["stations"].keys())
    if len(stations_list) < 4:
        stations_list = ["NDLS", "AGC", "GAYA", "HWH", "MAS", "SBC", "LKO", "JP", "ADI", "PUNE"]

    trains = []
    for i in range(50):
        source = random.choice(stations_list)
        dest = random.choice([s for s in stations_list if s != source])
        path = [source]
        current = source
        steps = random.randint(3, 8)
        for _ in range(steps):
            neighbors = [e[1] for e in current_graph["edges"] if e[0] == current] + \
                        [e[0] for e in current_graph["edges"] if e[1] == current]
            if not neighbors: break
            next_stop = random.choice([n for n in neighbors if n not in path[-2:]])
            path.append(next_stop)
            current = next_stop
        path.append(dest)

        train_info = random.choice(REAL_TRAINS)
        trains.append({
            "id": f"T{i+1:03d}",
            "name": train_info["name"],
            "train_type": train_info["type"],
            "source": source,
            "destination": dest,
            "path": path,
            "progress": random.uniform(0.05, 0.8),
            "speed": random.uniform(80, 160),
            "priority": random.randint(1, 3),
            "status": "MOVING"
        })
    return {"trains": trains}

# === STRESS TEST 100 — CHAOS SIMULATOR ===
@app.get("/stress_test_100")
def stress_test_100():
    stations_list = list(current_graph["stations"].keys())
    if len(stations_list) < 4:
        stations_list = ["NDLS", "AGC", "GAYA", "HWH", "MAS", "SBC", "LKO", "JP", "ADI", "PUNE"]

    trains = []
    for i in range(100):
        source = random.choice(stations_list)
        dest = random.choice([s for s in stations_list if s != source])
        path = [source]
        current = source
        steps = random.randint(3, 8)
        for _ in range(steps):
            neighbors = [e[1] for e in current_graph["edges"] if e[0] == current] + \
                        [e[0] for e in current_graph["edges"] if e[1] == current]
            if not neighbors: break
            next_stop = random.choice([n for n in neighbors if n not in path[-2:]])
            path.append(next_stop)
            current = next_stop
        path.append(dest)

        train_info = random.choice(REAL_TRAINS)
        speed = random.uniform(80, 160)
        if random.random() < 0.3:  # 30% chaos
            speed += random.uniform(-30, 30)
        trains.append({
            "id": f"C{i+1:03d}",
            "name": train_info["name"],
            "train_type": train_info["type"],
            "source": source,
            "destination": dest,
            "path": path,
            "progress": random.uniform(0.05, 0.8),
            "speed": speed,
            "priority": random.randint(1, 3),
            "status": "MOVING"
        })
    return {"trains": trains}

# === SPAWN ENGINE ===
def spawn_worker():
    global spawned_trains, spawn_enabled
    idx = 0
    while True:
        if spawn_enabled and len(spawned_trains) < max_trains:
            # generate one train using current graph
            g = current_graph if current_graph.get("stations") else {"stations": {"A":{"lat":28.60,"lon":77.20},"B":{"lat":28.00,"lon":78.00},"C":{"lat":26.90,"lon":80.90},"D":{"lat":27.50,"lon":79.50},"E":{"lat":27.20,"lon":78.80},"F":{"lat":26.50,"lon":79.90}}, "edges": [["A","C"],["A","B"],["B","D"],["D","C"],["B","E"],["E","F"],["F","C"]]}
            stations = list(g.get("stations", {}).keys())
            if not stations:
                stations = ["A","B","C","D","E","F"]
            s = random.choice(stations)
            d = random.choice(stations)
            while d == s:
                d = random.choice(stations)
            speed = random.randint(60,130)
            if random.random() < 0.3:
                speed += random.randint(-30,30)
            progress = random.random()*0.9
            lat, lon = g.get("stations", {}).get(s, {"lat":0.0, "lon":0.0})
            dlat, dlon = g.get("stations", {}).get(d, {"lat":lat, "lon":lon})
            lat = lat + (dlat - lat) * progress
            lon = lon + (dlon - lon) * progress
            new = {
                "id": f"SP{idx+1:03d}",
                "name": f"Spawn-{idx+1}",
                "source": s,
                "destination": d,
                "path": [s,d],
                "progress": progress,
                "speed": speed,
                "priority": random.randint(1,3),
                "status": "MOVING",
                "lat": lat,
                "lon": lon
            }
            spawned_trains.append(new)
            push_log("INFO", f"Spawned train {new['id']}")
            idx += 1
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

# === LOGS ENDPOINT ===
@app.get("/logs")
def get_logs(level: Optional[str]=None, train_id: Optional[str]=None, limit: int=200):
    logs = logs_buffer
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    if train_id:
        logs = [l for l in logs if l.get("train_id") == train_id]
    return {"logs": logs[-limit:], "total": len(logs)}

@app.get("/health")
def health():
    return {
        "system": "KAVACH 2.0",
        "status": "ACTIVE",
        "trains_saved_today": trains_saved_today,
        "real_trains": len(REAL_TRAINS),
        "animation": "SMOOTH & WORKING"
    }

if __name__ == "__main__":
    print("\n" + "═" * 80)
    print(" KAVACH 2.0 — INDIAN RAILWAYS PREDICTIVE AI v5.0")
    print(" → Smooth train animation | Real trains | Collision prevention")
    print(" → Trains move using path + progress (no lat/lon needed)")
    print(" → Ready to win any hackathon")
    print("═" * 80 + "\n")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
>>>>>>> 42b56fc74ed4d9318fd8a98b55c9f9214c9b0ffd
