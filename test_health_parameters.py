#!/usr/bin/env python3
"""
Thorough test suite for computeHealthParameters.py integration
"""

import json
import time
import sys
from typing import Dict, List

# Import the modules to test
try:
    from computeHealthParameters import compute_health_parameters
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
    """Test basic functionality of compute_health_parameters"""
    print("Testing basic functionality...")

    trains, _, _ = load_test_data()

    # Test with basic train data
    try:
        health_params = compute_health_parameters(trains)
        print(f"✓ Successfully computed health parameters for {len(health_params)} trains")

        # Verify structure
        if not isinstance(health_params, dict):
            print("✗ Health parameters should be a dict")
            return False

        for train_id, params in health_params.items():
            if not isinstance(params, dict):
                print(f"✗ Parameters for {train_id} should be a dict")
                return False

            # Check for required parameters p101-p120
            for i in range(101, 121):
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
        {"id": "T2", "lat": 28.60, "lon": 77.20},  # Partial telemetry
        {"id": "T3", "lat": 28.60, "lon": 77.20, "speed": 100},  # More telemetry
    ]

    try:
        health_params = compute_health_parameters(test_trains)
        print(f"✓ Handled missing telemetry for {len(health_params)} trains")

        # Verify deterministic behavior (same input should give same output)
        health_params2 = compute_health_parameters(test_trains)
        if health_params != health_params2:
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
            "mileage_km": 1000000,  # Very high mileage
            "last_maintenance_days": 1000,  # Very overdue
            "brake_pad_mm": 0.1,  # Very worn
            "wheel_profile_mm": 1.0,  # Very worn
            "engine_temp_c": 200,  # Very hot
            "battery_health_pct": 5,  # Very low
            "vibration_rms": 5.0,  # Very high vibration
            "rolling_resistance_delta": 1.0,  # Very high resistance
            "operator_reported_issues": 20,  # Many issues
        },
        {
            "id": "T2",
            "mileage_km": 0,  # New train
            "last_maintenance_days": 0,  # Just maintained
            "brake_pad_mm": 50,  # New pads
            "wheel_profile_mm": 30,  # New wheels
            "engine_temp_c": 80,  # Normal temp
            "battery_health_pct": 100,  # Perfect battery
            "vibration_rms": 0.0,  # No vibration
            "rolling_resistance_delta": 0.0,  # Perfect resistance
            "operator_reported_issues": 0,  # No issues
        }
    ]

    try:
        health_params = compute_health_parameters(extreme_trains)
        print("✓ Handled extreme values without errors")

        # Check that extreme values produce expected results
        t1_params = health_params["T1"]
        t2_params = health_params["T2"]

        # T1 should have higher (worse) values than T2 for most parameters
        worse_count = 0
        for i in range(101, 121):
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

        if "health_params" not in result:
            print("✗ Health parameters not found in compute140Parameters result")
            return False

        health_params = result["health_params"]
        print(f"✓ Health parameters integrated, computed for {len(health_params)} trains")

        # Verify structure matches standalone computation
        standalone_health = compute_health_parameters(trains)

        if health_params != standalone_health:
            print("✗ Integrated health params differ from standalone computation")
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
            "mileage_km": i * 1000,
            "last_maintenance_days": i * 10,
            "brake_pad_mm": 40 - (i % 40),
            "wheel_profile_mm": 25 - (i % 25),
            "engine_temp_c": 80 + (i % 20),
            "battery_health_pct": 100 - (i % 100),
            "vibration_rms": i % 2,
            "rolling_resistance_delta": (i % 10) / 100,
            "operator_reported_issues": i % 5,
        }
        large_trains.append(train)

    try:
        start_time = time.time()
        health_params = compute_health_parameters(large_trains)
        end_time = time.time()

        duration = end_time - start_time
        print(f"✓ Computed health parameters for 100 trains in {duration:.3f} seconds")

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
        {"id": "T1", "mileage_km": float('inf')},  # Infinite values
        {"id": "T2", "mileage_km": float('nan')},  # NaN values
        {"id": "T3", "brake_pad_mm": -10},  # Negative values
        {"id": "T4", "battery_health_pct": 150},  # Values > 100%
    ]

    try:
        health_params = compute_health_parameters(edge_case_trains)
        print(f"✓ Handled edge cases, computed for {len(health_params)} valid trains")

        # Should skip invalid IDs
        if None in health_params or "" in health_params:
            print("✗ Should skip trains with invalid IDs")
            return False

        # Should handle invalid numeric values gracefully
        for train_id in ["T1", "T2", "T3", "T4"]:
            if train_id in health_params:
                params = health_params[train_id]
                for param_key, value in params.items():
                    if not (0.0 <= value <= 1.0):
                        print(f"✗ Parameter {param_key} out of range [0,1]: {value}")
                        return False

        print("✓ Edge cases handled gracefully")
        return True

    except Exception as e:
        print(f"✗ Error in edge cases test: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting thorough testing of computeHealthParameters integration\n")

    tests = [
        test_basic_functionality,
        test_missing_telemetry,
        test_extreme_values,
        test_integration,
        test_performance,
        test_edge_cases,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Health parameters integration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
