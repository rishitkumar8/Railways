import json
from computeNetworkLoadParameters import compute_network_load_parameters

# Test edge cases

# 1. Empty train list
results_empty = compute_network_load_parameters([], [], [])
print("Empty trains test: Passed" if results_empty == {} else "Failed")

# 2. No edges
with open('test_data.json', 'r') as f:
    data = json.load(f)
trains = data['trains']
stations = list(data['graph']['stations'].keys())
results_no_edges = compute_network_load_parameters(trains, stations, [])
print("No edges test: Passed" if len(results_no_edges) == len(trains) else "Failed")

# 3. Trains without paths
trains_no_path = [{"id": "T1", "source": "A"}, {"id": "T2", "source": "B"}]
results_no_path = compute_network_load_parameters(trains_no_path, ["A", "B"], [{"source": "A", "target": "B"}])
print("No path test: Passed" if len(results_no_path) == 2 else "Failed")

# 4. Trains without source
trains_no_source = [{"id": "T1", "path": ["A", "B"]}, {"id": "T2", "path": ["B", "A"]}]
results_no_source = compute_network_load_parameters(trains_no_source, ["A", "B"], [{"source": "A", "target": "B"}])
print("No source test: Passed" if len(results_no_source) == 2 else "Failed")

# 5. With collision params
collision_params = {"T1": {"p61": 0.5}}
results_with_collision = compute_network_load_parameters(trains[:1], stations, edges, collision_params)
print("Collision params test: Passed" if len(results_with_collision) == 1 else "Failed")

# 6. Deterministic check - run twice
results1 = compute_network_load_parameters(trains, stations, edges)
results2 = compute_network_load_parameters(trains, stations, edges)
deterministic = all(
    all(abs(results1[tid][p] - results2[tid][p]) < 1e-6 for p in results1[tid])
    for tid in results1
)
print("Deterministic test: Passed" if deterministic else "Failed")

print("Edge case tests completed.")
