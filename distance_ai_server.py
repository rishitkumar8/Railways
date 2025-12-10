from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import math
import heapq
import logging
from typing import List, Dict, Optional, Tuple, Set

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("railway_ai")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SAFE_DISTANCE = 1200     # meters
LOOKAHEAD = 20           # seconds
blocked_edges: Set[Tuple[str, str]] = set()


# ---------------- MODELS ----------------

class Train(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    source: str
    destination: str
    path: List[str]
    progress: float = 0.0
    priority: int = 1
    speed: float = 100.0


class GraphModel(BaseModel):
    stations: Dict[str, Dict[str, float]]
    edges: List[List[str]]


class InputModel(BaseModel):
    trains: List[Train]
    graph: GraphModel


class ApplyModel(BaseModel):
    train_id: str
    new_path: List[str]


# ---------------- UTILITIES ----------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(a))


def dijkstra(graph: GraphModel, start: str, goal: str, blocked: Set[Tuple[str, str]]):
    stations = graph.stations

    # Build adjacency list but skip blocked edges
    adj = {node: [] for node in stations}
    for u, v in graph.edges:
        if (u, v) not in blocked and (v, u) not in blocked:
            adj[u].append(v)
            adj[v].append(u)

    dist = {node: float("inf") for node in adj}
    dist[start] = 0

    pq = [(0, start, [])]

    while pq:
        d, node, path = heapq.heappop(pq)

        if node == goal:
            return path + [node]

        for nei in adj[node]:
            d2 = haversine(
                stations[node]["lat"], stations[node]["lon"],
                stations[nei]["lat"], stations[nei]["lon"]
            )
            newd = d + d2
            if newd < dist[nei]:
                dist[nei] = newd
                heapq.heappush(pq, (newd, nei, path + [node]))

    return None


# ---------------- MAIN AI LOGIC ----------------

@app.post("/decide")
def decide(data: InputModel):
    trains = data.trains
    graph = data.graph

    for i in range(len(trains)):
        for j in range(i+1, len(trains)):
            A = trains[i]
            B = trains[j]

            # Simple lookahead: use current positions
            dist = haversine(A.lat, A.lon, B.lat, B.lon)

            if dist < SAFE_DISTANCE:
                logger.warning(f"⚠ COLLISION DETECTED between {A.id} and {B.id}")

                # Determine low-priority train
                low = B if A.priority > B.priority else A

                # Mark its current edge blocked
                idx = min(int(low.progress * (len(low.path)-1)), len(low.path)-2)
                blocked_edge = (low.path[idx], low.path[idx+1])
                blocked_edges.add(blocked_edge)

                logger.info(f"🚫 BLOCKED EDGE: {blocked_edge}")

                # Try rerouting
                new_path = dijkstra(
                    graph,
                    start=low.path[idx],
                    goal=low.destination,
                    blocked=blocked_edges
                )

                if new_path:
                    reason = (
                        f"Original path blocked at {blocked_edge}. "
                        f"AI chose shortest safe path: {' → '.join(new_path)}"
                    )

                    return {
                        "action": "REQUEST_CONFIRMATION",
                        "train_id": low.id,
                        "suggested_path": new_path,
                        "reason": reason
                    }

                return {"action": "STOP_BOTH", "reason": "No safe alternative path"}

    return {"action": "NORMAL"}


# ---------------- APPLY CONFIRMED REROUTE ----------------

@app.post("/apply_reroute")
def apply_reroute(model: ApplyModel):
    logger.info(f"✔ USER CONFIRMED NEW PATH FOR {model.train_id}: {model.new_path}")
    return {"status": "ok", "train_id": model.train_id, "new_path": model.new_path}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("distance_ai_server:app", host="0.0.0.0", port=8001, reload=True)
