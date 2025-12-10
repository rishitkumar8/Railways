# computeNetworkLoadParameters.py
"""
Network Load / Congestion / Scheduling Parameters
Produces p41–p60 for every train.
Inputs:
    trains: list of train dicts
    stations: list of station dicts
    edges: list of edges {source, target}
    collisionParams: dict of p61–p80 (optional influence)
"""

from typing import List, Dict
import math
from collections import defaultdict

def compute_network_load_parameters(
    trains: List[Dict],
    stations: List[Dict],
    edges: List[Dict],
    collision_params: Dict[str, Dict[str, float]] = None
) -> Dict[str, Dict[str, float]]:

    results = {}

    # --------------------------
    # Build adjacency map
    # --------------------------
    graph = defaultdict(list)
    for e in edges:
        graph[e["source"]].append(e["target"])
        graph[e["target"]].append(e["source"])

    # --------------------------
    # Compute station load counts
    # --------------------------
    station_load = defaultdict(int)
    for t in trains:
        if t.get("source"):
            station_load[t["source"]] += 1

    # normalize station load
    max_station_load = max(station_load.values()) if station_load else 1

    # --------------------------
    # Compute edge load counts
    # --------------------------
    edge_load = defaultdict(int)
    for t in trains:
        path = t.get("path", [])
        for i in range(len(path) - 1):
            a, b = path[i], path[i+1]
            key = tuple(sorted([a, b]))
            edge_load[key] += 1

    max_edge_load = max(edge_load.values()) if edge_load else 1

    # --------------------------
    # Global congestion factor
    # --------------------------
    total_edges = len(edges)
    total_trains = len(trains)
    avg_congestion = total_trains / max(1, total_edges)

    # --------------------------
    # Compute parameters for each train
    # --------------------------
    for t in trains:
        tid = t["id"]
        source = t.get("source")
        path = t.get("path", [])

        # ----------------------------------------------
        # P41 — Station load pressure (0..1)
        # ----------------------------------------------
        p41 = station_load[source] / max_station_load if source else 0.0

        # ----------------------------------------------
        # P42 — Path load index (avg load per edge)
        # ----------------------------------------------
        if len(path) > 1:
            loads = []
            for i in range(len(path)-1):
                key = tuple(sorted([path[i], path[i+1]]))
                loads.append(edge_load[key] / max_edge_load)
            p42 = sum(loads) / len(loads)
        else:
            p42 = 0.0

        # ----------------------------------------------
        # P43 — Network-wide congestion factor
        # ----------------------------------------------
        # Scaled to 0..1
        p43 = min(1.0, avg_congestion / 10.0)

        # ----------------------------------------------
        # P44 — Schedule deviation risk
        # ----------------------------------------------
        speed = t.get("speed", 0)
        ideal_speed = 120.0
        p44 = min(1.0, abs(ideal_speed - speed) / ideal_speed)

        # ----------------------------------------------
        # P45 — Path conflict probability
        # ----------------------------------------------
        # If more trains share the same edges, probability rises.
        p45 = p42 * 0.8 + p43 * 0.2

        # ----------------------------------------------
        # P46 — Bottleneck severity
        # ----------------------------------------------
        # highest-load edge in the train's path
        if len(path) > 1:
            local_max = 0.0
            for i in range(len(path)-1):
                key = tuple(sorted([path[i], path[i+1]]))
                local_max = max(local_max, edge_load[key] / max_edge_load)
            p46 = local_max
        else:
            p46 = 0.0

        # ----------------------------------------------
        # P47 — Reroute pressure (need to find alternate path)
        # ----------------------------------------------
        p47 = min(1.0, p46 * 1.25)

        # ----------------------------------------------
        # P48 — Flow efficiency
        # ----------------------------------------------
        # More congestion = lower efficiency
        p48 = 1.0 - p42

        # ----------------------------------------------
        # P49 — Travel time inflation factor due to congestion
        # ----------------------------------------------
        p49 = min(1.0, p42 * 1.2)

        # ----------------------------------------------
        # P50 — Station dwell expansion
        # ----------------------------------------------
        p50 = min(1.0, p41 * 0.9)

        # ----------------------------------------------
        # P51 — Edge density index
        # ----------------------------------------------
        p51 = avg_congestion / 5.0
        p51 = min(1.0, p51)

        # ----------------------------------------------
        # P52 — Global throughput stress index
        # ----------------------------------------------
        p52 = min(1.0, (total_trains / max(1, total_edges)) / 8.0)

        # ----------------------------------------------
        # P53 — Network entropy (path diversity)
        # ----------------------------------------------
        unique_stations = len({t["source"] for t in trains})
        p53 = min(1.0, unique_stations / max(1, len(stations)))

        # ----------------------------------------------
        # P54 — Demand/supply imbalance
        # ----------------------------------------------
        p54 = abs(p41 - p43)

        # ----------------------------------------------
        # P55 — Uni-directional overload index
        # ----------------------------------------------
        if len(path) > 1:
            overload_count = 0
            for i in range(len(path)-1):
                key = tuple(sorted([path[i], path[i+1]]))
                if edge_load[key] > (0.7 * max_edge_load):
                    overload_count += 1
            p55 = min(1.0, overload_count / max(1, len(path)-1))
        else:
            p55 = 0.0

        # ----------------------------------------------
        # P56 — Localized edge group density
        # ----------------------------------------------
        p56 = sum(edge_load.values()) / (max_edge_load * max(1, len(edge_load)))
        p56 = min(1.0, p56)

        # ----------------------------------------------
        # P57 — Congestion amplification due to collisions
        # ----------------------------------------------
        col_val = 0.0
        if collision_params and tid in collision_params:
            col_val = collision_params[tid].get("p61", 0.0)
        p57 = min(1.0, (p42 + col_val) / 2.0)

        # ----------------------------------------------
        # P58 — Expected schedule drift
        # ----------------------------------------------
        p58 = min(1.0, (p44 + p49 + p50) / 3.0)

        # ----------------------------------------------
        # P59 — Real-time routing difficulty
        # ----------------------------------------------
        p59 = min(1.0, p47 * 0.8 + p45 * 0.2)

        # ----------------------------------------------
        # P60 — Network load composite index
        # ----------------------------------------------
        p60 = (p41 + p42 + p43 + p46 + p49 + p55) / 6.0

        results[tid] = {
            "p41": p41, "p42": p42, "p43": p43, "p44": p44, "p45": p45,
            "p46": p46, "p47": p47, "p48": p48, "p49": p49, "p50": p50,
            "p51": p51, "p52": p52, "p53": p53, "p54": p54, "p55": p55,
            "p56": p56, "p57": p57, "p58": p58, "p59": p59, "p60": p60
        }

    return results
