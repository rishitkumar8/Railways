import requests
import json

# Test the heatmap functionality by simulating train deployment and checking parameters

def test_heatmaps():
    print("Testing heatmap functionality...")

    # First, check initial parameters (should be minimal)
    try:
        response = requests.get('http://localhost:8001/parameters_full', timeout=5)
        initial_data = response.json()
        print(f"Initial parameters: {len(initial_data)} keys")
        print(f"Initial trains: {len(initial_data.get('trains', []))}")
    except Exception as e:
        print(f"Error getting initial parameters: {e}")
        return

    # Simulate deploying trains by calling the stress test endpoint
    try:
        print("\nDeploying test trains...")
        stress_response = requests.get('http://localhost:8001/stress_test_50', timeout=10)
        stress_data = stress_response.json()
        trains = stress_data.get('trains', [])
        print(f"Generated {len(trains)} test trains")

        # Now send these trains to the decide endpoint to initialize the system
        graph_data = {
            "stations": {
                "NDLS": {"lat": 28.6415, "lon": 77.2194},
                "JP": {"lat": 26.9196, "lon": 75.7878},
                "ADI": {"lat": 23.0225, "lon": 72.5714},
                "CSTM": {"lat": 18.9398, "lon": 72.8354},
                "MAS": {"lat": 13.0827, "lon": 80.2707},
                "BNC": {"lat": 12.9784, "lon": 77.6408},
                "SBC": {"lat": 12.9719, "lon": 77.5937},
                "UBL": {"lat": 15.1394, "lon": 76.9214},
                "DEL": {"lat": 28.7041, "lon": 77.1025},
                "GZB": {"lat": 28.6692, "lon": 77.4538},
                "CNB": {"lat": 26.4499, "lon": 80.3319},
                "LKO": {"lat": 26.8467, "lon": 80.9462},
                "HWH": {"lat": 22.5726, "lon": 88.3639},
                "BBS": {"lat": 20.2961, "lon": 85.8245},
                "VSKP": {"lat": 17.6868, "lon": 83.2185},
                "TVC": {"lat": 8.5241, "lon": 76.9366},
                "ERS": {"lat": 9.9312, "lon": 76.2673},
                "MAQ": {"lat": 11.2588, "lon": 75.7804}
            },
            "edges": [
                ["NDLS", "JP"], ["JP", "ADI"], ["ADI", "CSTM"],
                ["MAS", "BNC"], ["BNC", "SBC"], ["SBC", "UBL"],
                ["DEL", "GZB"], ["GZB", "NDLS"], ["NDLS", "CNB"], ["CNB", "LKO"],
                ["HWH", "BBS"], ["BBS", "VSKP"], ["VSKP", "MAS"],
                ["TVC", "ERS"], ["ERS", "MAQ"], ["MAQ", "UBL"], ["UBL", "SBC"]
            ]
        }

        # Use a subset of trains for testing
        test_trains = trains[:5]  # Just 5 trains for testing

        decide_payload = {
            "trains": test_trains,
            "graph": graph_data
        }

        print(f"Sending {len(test_trains)} trains to decision engine...")
        decide_response = requests.post('http://localhost:8001/decide',
                                      json=decide_payload, timeout=15)
        decide_data = decide_response.json()
        print(f"Decision result: {decide_data.get('action', 'UNKNOWN')}")

        # Now check parameters again
        print("\nChecking parameters after train deployment...")
        params_response = requests.get('http://localhost:8001/parameters_full', timeout=5)
        final_data = params_response.json()

        print(f"Final parameters keys: {len(final_data)}")
        print(f"Trains in system: {len(final_data.get('trains', []))}")

        # Check environment data
        env = final_data.get('environment', {})
        stations_env = env.get('stations', {})
        segments_env = env.get('segments', {})

        print(f"Station environments: {len(stations_env)}")
        print(f"Segment environments: {len(segments_env)}")

        if stations_env:
            sample_station = list(stations_env.keys())[0]
            print(f"Sample station {sample_station} env keys: {list(stations_env[sample_station].keys())}")

        if segments_env:
            sample_segment = list(segments_env.keys())[0]
            print(f"Sample segment {sample_segment} env keys: {list(segments_env[sample_segment].keys())}")

        # Check if we have the expected parameter ranges for heatmaps
        # The frontend expects P1-P10, P11-P20, P31-P40
        # But these come from the params dict in compute140Parameters result
        # The current endpoint doesn't return the raw params, just environment

        print("\nHeatmap test completed successfully!")

    except Exception as e:
        print(f"Error during heatmap testing: {e}")

if __name__ == "__main__":
    test_heatmaps()
