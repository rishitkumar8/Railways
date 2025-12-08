#!/usr/bin/env python3
"""
Thorough test suite for computeSafetyParameters.py integration
"""

import json
import time
import sys
from typing import Dict, List

# Import the modules to test
try:
    from computeSafetyParameters import compute_safety_parameters
    from compute140Parameters import compute140Parameters
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def load_test_data():
    """Load test data from test_data.json"""
    try:
        with open('test_data.json', 'r') as f:
            data = json.load(f)
        return data['trains'], data['graph']['stations'], data['graph']['edges']
    except Exception as e:
        print(f"Error loading test data: {e}")
        sys.exit(1)

def test_basic_functionality():
    """Test basic functionality of compute_safety_parameters"""
    print("Testing basic functionality...")

    trains, _, _ = load_test_data()

    # Test with basic train data
    try:
        safety_params = compute_safety_parameters(trains)
        print(f"✓ Successfully computed safety parameters for {len(safety_params)} trains")

        # Verify structure
        if not isinstance(safety_params, dict):
            print("✗ Safety parameters should be a dict")
            return False

        for train_id, params in safety_params.items():
            if not isinstance(params, dict):
                print(f"✗ Parameters for {train_id} should be a dict")
                return False

            # Check for required parameters p121-p140
            for i in range(121, 141):
                param_key = f"p{i}"
                if param_key not in params:
                    print(f"✗ Missing parameter {param_key} for train {train_id}")
                    return False

                value = params[param_key]
                if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                    print(f"✗ Parameter {param_key} for train {train_id} should be float in [0,1], got {value}")
                    return False

        print("✓ All parameters present and in valid range")
        return True

    except Exception as e:
        print(f"✗ Error in basic functionality test: {e}")
        return False

def test_missing_telemetry():
    """Test with missing telemetry fields"""
    print("Testing missing telemetry handling...")

    # Create train with missing fields
    test_trains = [
        {"id": "T1"},  # Minimal train
        {"id": "T2", "speed": 50},  # Partial telemetry
        {"id": "T3", "speed": 100, "driver_fatigue": 0.5, "weather_data": {"rain_mm": 10}},  # More telemetry
    ]

    try:
        safety_params = compute_safety_parameters(test_trains)
        print(f"✓ Handled missing telemetry for {len(safety_params)} trains")

        # Verify deterministic behavior (same input should give same output)
        safety_params2 = compute_safety_parameters(test_trains)
        if safety_params != safety_params2:
            print("✗ Non-deterministic behavior with missing telemetry")
            return False

        print("✓ Deterministic behavior confirmed")
        return True

    except Exception as e:
        print(f"✗ Error in missing telemetry test: {e}")
        return False

def test_extreme_values():
    """Test with extreme values"""
    print("Testing extreme values...")

    extreme_trains = [
        {
            "id": "T1",
            "speed": 200,  # Very high speed
            "driver_fatigue": 1.0,  # Extremely fatigued
            "weather_data": {
                "rain_mm": 50,  # Heavy rain
                "wind_kmh": 100,  # Strong wind
                "temp_c": 50,  # Very hot
                "humidity_pct": 100  # High humidity
            },
            "visibility_m": 10,  # Very poor visibility
            "signal_quality": 0.0,  # Poor signal
            "spad_events": 20,  # Many SPAD events
            "emergency_brake_count": 30,  # Many emergency brakes
            "noise_dba": 120,  # Very loud
            "vibration_rms": 3.0,  # High vibration
            "track_curvature_risk": 1.0,  # High curvature risk
        },
        {
            "id": "T2",
            "speed": 0,  # Stationary
            "driver_fatigue": 0.0,  # Fully rested
            "weather_data": {
                "rain_mm": 0,  # No rain
                "wind_kmh": 0,  # No wind
                "temp_c": 20,  # Normal temp
                "humidity_pct": 30  # Low humidity
            },
            "visibility_m": 10000,  # Perfect visibility
            "signal_quality": 1.0,  # Perfect signal
            "spad_events": 0,  # No SPAD events
            "emergency_brake_count": 0,  # No emergency brakes
            "noise_dba": 60,  # Quiet
            "vibration_rms": 0.0,  # No vibration
            "track_curvature_risk": 0.0,  # No curvature risk
        }
    ]

    try:
        safety_params = compute_safety_parameters(extreme_trains)
        print("✓ Handled extreme values without errors")

        # Check that extreme values produce expected results
        t1_params = safety_params["T1"]
        t2_params = safety_params["T2"]

        # T1 should have higher (worse) values than T2 for most parameters
        worse_count = 0
        for i in range(121, 141):
            param = f"p{i}"
            if t1_params[param] > t2_params[param]:
                worse_count += 1

        if worse_count < 15:  # Expect most parameters to be worse for T1
            print(f"✗ Extreme values not reflected properly (only {worse_count}/20 parameters worse)")
            return False

        print("✓ Extreme values correctly reflected in parameters")
        return True

    except Exception as e:
        print(f"✗ Error in extreme values test: {e}")
        return False

def test_integration():
    """Test integration with compute140Parameters"""
    print("Testing integration with compute140Parameters...")

    trains, stations, edges = load_test_data()
    # Convert edges to tuples as expected by the function
    edges = [tuple(edge) for edge in edges]

    try:
        result = compute140Parameters(trains, stations, edges)

        if "safety_params" not in result:
            print("✗ Safety parameters not found in compute140Parameters result")
            return False

        safety_params = result["safety_params"]
        print(f"✓ Safety parameters integrated, computed for {len(safety_params)} trains")

        # Verify structure matches standalone computation
        standalone_safety = compute_safety_parameters(trains)

        if safety_params != standalone_safety:
            print("✗ Integrated safety params differ from standalone computation")
            return False

        print("✓ Integration results match standalone computation")
        return True

    except Exception as e:
        print(f"✗ Error in integration test: {e}")
        return False

def test_performance():
    """Test performance with large dataset"""
    print("Testing performance...")

    # Create larger dataset (100 trains)
    large_trains = []
    for i in range(100):
        train = {
            "id": f"T{i}",
            "speed": i * 2,
            "driver_fatigue": (i % 10) / 10.0,
            "weather_data": {
                "rain_mm": i % 20,
                "wind_kmh": i % 50,
                "temp_c": 15 + (i % 20),
                "humidity_pct": 40 + (i % 60)
            },
            "visibility_m": 2000 - (i % 2000),
            "signal_quality": 1.0 - (i % 10) / 10.0,
            "spad_events": i % 5,
            "emergency_brake_count": i % 10,
            "noise_dba": 70 + (i % 30),
            "vibration_rms": (i % 20) / 10.0,
            "track_curvature_risk": (i % 10) / 10.0,
        }
        large_trains.append(train)

    try:
        start_time = time.time()
        safety_params = compute_safety_parameters(large_trains)
        end_time = time.time()

        duration = end_time - start_time
        print(f"✓ Computed safety parameters for 100 trains in {duration:.3f} seconds")

        if duration > 1.0:  # Should be fast
            print(f"⚠ Performance warning: {duration:.3f}s for 100 trains")
        else:
            print("✓ Performance acceptable")

        return True

    except Exception as e:
        print(f"✗ Error in performance test: {e}")
        return False

def test_edge_cases():
    """Test various edge cases"""
    print("Testing edge cases...")

    edge_case_trains = [
        {"id": None},  # Invalid ID
        {"id": ""},    # Empty ID
        {"id": "T1", "speed": float('inf')},  # Infinite values
        {"id": "T2", "speed": float('nan')},  # NaN values
        {"id": "T3", "driver_fatigue": -1.0},  # Negative values
        {"id": "T4", "weather_data": {"rain_mm": -10}},  # Negative weather
        {"id": "T5", "signal_quality": 2.0},  # Values > 1.0
    ]

    try:
        safety_params = compute_safety_parameters(edge_case_trains)
        print(f"✓ Handled edge cases, computed for {len(safety_params)} valid trains")

        # Should skip invalid IDs
        if None in safety_params or "" in safety_params:
            print("✗ Should skip trains with invalid IDs")
            return False

        # Should handle invalid numeric values gracefully
        for train_id in ["T1", "T2", "T3", "T4", "T5"]:
            if train_id in safety_params:
                params = safety_params[train_id]
                for param_key, value in params.items():
                    if not (0.0 <= value <= 1.0):
                        print(f"✗ Parameter {param_key} out of range [0,1]: {value}")
                        return False

        print("✓ Edge cases handled gracefully")
        return True

    except Exception as e:
        print(f"✗ Error in edge cases test: {e}")
        return False

def test_weather_influence():
    """Test weather influence on parameters"""
    print("Testing weather influence...")

    base_train = {
        "id": "T1",
        "speed": 80,
        "driver_fatigue": 0.2,
        "visibility_m": 1000,
        "signal_quality": 0.8,
        "spad_events": 1,
        "emergency_brake_count": 2,
        "noise_dba": 75,
        "vibration_rms": 0.5,
        "track_curvature_risk": 0.3,
    }

    # Test different weather conditions
    weather_scenarios = [
        {"rain_mm": 0, "wind_kmh": 0, "temp_c": 20, "humidity_pct": 50},  # Good weather
        {"rain_mm": 20, "wind_kmh": 50, "temp_c": 40, "humidity_pct": 90},  # Bad weather
    ]

    results = []
    for weather in weather_scenarios:
        test_train = base_train.copy()
        test_train["weather_data"] = weather
        safety_params = compute_safety_parameters([test_train])
        results.append(safety_params["T1"])

    good_weather = results[0]
    bad_weather = results[1]

    # Bad weather should generally have higher risk values
    higher_risk_count = 0
    for i in range(121, 141):
        param = f"p{i}"
        if bad_weather[param] > good_weather[param]:
            higher_risk_count += 1

    if higher_risk_count < 5:  # Expect some parameters to be worse in bad weather
        print(f"✗ Weather influence not properly reflected (only {higher_risk_count}/20 parameters worse)")
        return False

    print("✓ Weather conditions properly influence safety parameters")
    return True

def main():
    """Run all tests"""
    print("Starting thorough testing of computeSafetyParameters integration\n")

    tests = [
        test_basic_functionality,
        test_missing_telemetry,
        test_extreme_values,
        test_integration,
        test_performance,
        test_edge_cases,
        test_weather_influence,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Safety parameters integration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
