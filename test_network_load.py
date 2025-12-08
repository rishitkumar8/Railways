import json
from computeNetworkLoadParameters import compute_network_load_parameters

# Load test data
with open('test_data.json', 'r') as f:
    data = json.load(f)

trains = data['trains']
stations = list(data['graph']['stations'].keys())
edges = [{'source': e[0], 'target': e[1]} for e in data['graph']['edges']]

# Test the function
results = compute_network_load_parameters(trains, stations, edges)

# Basic checks
print("Import and basic execution successful.")
print(f"Number of results: {len(results)}")
print(f"Expected: {len(trains)}")

# Check a sample result
if results:
    sample_train = list(results.keys())[0]
    sample_params = results[sample_train]
    print(f"Sample train {sample_train} parameters: {list(sample_params.keys())}")
    print(f"All params present: {all(f'p{i}' in sample_params for i in range(41, 61))}")

    # Check ranges
    all_in_range = all(0 <= v <= 1 for v in sample_params.values())
    print(f"All values in [0,1]: {all_in_range}")

print("Basic test completed.")
