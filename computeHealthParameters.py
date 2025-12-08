"""
Train Health / Mechanical Condition Parameters (P101..P120)

Each train receives a dict with p101..p120 in range 0..1 (higher = worse).
Inputs:
  trains: list of dicts. Optional useful fields per train:
    - id (required)
    - mileage_km (float)
    - last_maintenance_days (int)
    - brake_pad_mm (float)           # remaining brake pad thickness in mm
    - wheel_profile_mm (float)       # wheel tread/profile measure (mm)
    - engine_temp_c (float)
    - nominal_engine_temp_c (float)  # expected operating temp, default 85°C
    - battery_health_pct (0..100)
    - coupling_ok (bool)
    - vibration_rms (float)          # m/s^2 RMS vibration
    - rolling_resistance_delta (float) # fraction deviation from expected (0=ok, positive=bad)
    - oil_pressure_ok (bool)
    - maintenance_history_count (int)
    - operator_reported_issues (int)
    - last_service_mileage_km (float)
    - mass_kg (float)
    - axle_count (int)

Outputs (p101..p120):
  p101: brake_wear_index (higher = more worn)
  p102: wheel_wear_index
  p103: suspension_vibration_index
  p104: engine_temp_deviation
  p105: battery_health_index
  p106: coupling_integrity_index
  p107: electrical_stability_index
  p108: rolling_resistance_index
  p109: lubrication_oil_risk
  p110: brake_performance_risk (composite)
  p111: maintenance_overdue_index
  p112: sensor_health_index
  p113: brake_system_pressure_risk
  p114: axle_load_imbalance_index
  p115: gearbox_transmission_index
  p116: brake_disc_thinning_index
  p117: thermal_stress_index
  p118: fatigue_lifetime_index
  p119: human_reported_issue_index
  p120: train_health_composite (final composite risk)
"""

import hashlib
import math
from typing import List, Dict

# Helpers
def _seed_from_str(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")

def _rand0_1_from_seed(seed_int: int) -> float:
    return (seed_int % 1000003) / 1000003.0

def _clamp01(x: float) -> float:
    if x != x:
        return 0.0
    return max(0.0, min(1.0, x))

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    try:
        return a / b
    except Exception:
        return default

# Main function
def compute_health_parameters(trains: List[Dict]) -> Dict[str, Dict[str, float]]:
    results: Dict[str, Dict[str, float]] = {}

    for t in trains:
        tid = t.get("id", None)
        if tid is None or tid == "":
            continue

        # deterministic baseline (used when telemetry missing)
        seed = _seed_from_str(tid)
        rnd = _rand0_1_from_seed(seed)

        # --- Input extraction with defaults ---
        mileage_km = float(t.get("mileage_km", 0.0))           # total odometer
        last_maint_days = float(t.get("last_maintenance_days", 180.0))  # days since maintenance
        brake_pad_mm = t.get("brake_pad_mm", None)             # mm remaining; if None use baseline
        wheel_profile_mm = t.get("wheel_profile_mm", None)     # mm wear indicator
        engine_temp_c = float(t.get("engine_temp_c", 0.0))
        nominal_eng_c = float(t.get("nominal_engine_temp_c", 85.0))
        battery_pct = float(t.get("battery_health_pct", 80.0))
        coupling_ok = t.get("coupling_ok", True)
        vibration_rms = float(t.get("vibration_rms", 0.2))     # m/s^2
        rolling_resistance_delta = float(t.get("rolling_resistance_delta", 0.0))
        oil_pressure_ok = t.get("oil_pressure_ok", True)
        maintenance_history = int(t.get("maintenance_history_count", 1))
        reported_issues = int(t.get("operator_reported_issues", 0))
        last_service_mileage = float(t.get("last_service_mileage_km", mileage_km))
        mass_kg = float(t.get("mass_kg", 4e5))                 # default heavy train
        axle_count = int(t.get("axle_count", 24))

        # --- Baseline estimations if sensors missing ---
        # Brake pad: common thickness new ~ 40mm, critical threshold ~ 8mm
        if brake_pad_mm is None:
            # baseline wear increases with mileage and seed
            # estimate remaining = 40 - (mileage_km / 10000) * 40 * rnd
            est_wear = (mileage_km / 10000.0) * 40.0 * (0.5 + rnd * 0.5)
            brake_pad_mm = max(4.0, 40.0 - est_wear)

        if wheel_profile_mm is None:
            # new profile ~ 25mm, wear increases with mileage
            est = (mileage_km / 20000.0) * 25.0 * (0.4 + rnd * 0.6)
            wheel_profile_mm = max(4.0, 25.0 - est)

        # --- Parameter formulas (normalized 0..1 where 1 = bad) ---

        # P101 — brake_wear_index
        # map brake_pad_mm: 40mm -> 0.0 (new), 8mm -> 1.0 (critical)
        p101 = _clamp01(_safe_div(40.0 - brake_pad_mm, 40.0 - 8.0))

        # P102 — wheel_wear_index
        # wheel_profile: 25mm new -> 0, 6mm critical -> 1
        p102 = _clamp01(_safe_div(25.0 - wheel_profile_mm, 25.0 - 6.0))

        # P103 — suspension_vibration_index
        # higher RMS vibration is worse. Map 0.0..2.0 m/s^2 to 0..1
        p103 = _clamp01(vibration_rms / 2.0)

        # P104 — engine_temp_deviation
        # abs deviation from nominal; map 0..40°C deviation to 0..1
        p104 = _clamp01(abs(engine_temp_c - nominal_eng_c) / 40.0)

        # P105 — battery_health_index (higher = worse)
        p105 = _clamp01(1.0 - (battery_pct / 100.0))

        # P106 — coupling_integrity_index
        p106 = 0.0 if coupling_ok else 1.0

        # P107 — electrical_stability_index
        # infer from battery + random seed for unknown configs
        p107 = _clamp01(0.5 * p105 + 0.5 * (0.2 + 0.6 * rnd))

        # P108 — rolling_resistance_index
        # rolling_resistance_delta (fraction) positive -> worse. Map 0..0.2 to 0..1
        p108 = _clamp01(min(1.0, rolling_resistance_delta / 0.2))

        # P109 — lubrication_oil_risk (if oil pressure abnormal)
        p109 = 0.0 if oil_pressure_ok else 1.0

        # P110 — brake_performance_risk (composite)
        # combine brake wear, brake pad thickness, and vibration
        p110 = _clamp01(0.5 * p101 + 0.3 * p103 + 0.2 * p109)

        # P111 — maintenance_overdue_index
        # map last_maint_days 0..365 to 0..1 (365+ => 1.0)
        p111 = _clamp01(last_maint_days / 365.0)

        # P112 — sensor_health_index
        # if telemetry fields missing, risk increases
        telemetry_fields = ["lat", "lon", "speed"]
        missing = 0
        for f in telemetry_fields:
            if f not in t:
                missing += 1
        # map missing count 0..3 to 0..1
        p112 = _clamp01(min(1.0, missing / len(telemetry_fields)))

        # P113 — brake_system_pressure_risk
        # if train has 'brake_pressure_ok' flag, use inverse; else infer from p101/p110
        brake_pressure_ok = t.get("brake_pressure_ok", None)
        if brake_pressure_ok is None:
            p113 = _clamp01(0.6 * p110 + 0.4 * p101)
        else:
            p113 = 0.0 if brake_pressure_ok else 1.0

        # P114 — axle_load_imbalance_index
        # if axle_count and mass known, small random imbalance baseline; large imbalance if provided
        # check optional 'axle_load_imbalance' field (fraction e.g., 0.0..0.5)
        axle_imbalance = float(t.get("axle_load_imbalance", min(0.02 + rnd * 0.05, 0.1)))
        p114 = _clamp01(min(1.0, axle_imbalance / 0.5))

        # P115 — gearbox_transmission_index
        # rely on vibration, last service and seed
        p115 = _clamp01(0.4 * p103 + 0.3 * p111 + 0.3 * (0.2 + 0.6 * rnd))

        # P116 — brake_disc_thinning_index (proxy)
        # correlate with mileage since last service
        km_since_service = max(0.0, mileage_km - last_service_mileage)
        # map 0..200000 km to 0..1
        p116 = _clamp01(min(1.0, km_since_service / 200000.0))

        # P117 — thermal_stress_index
        # combine engine temp deviation and recent mileage
        p117 = _clamp01(0.6 * p104 + 0.4 * _clamp01(min(1.0, (mileage_km / 100000.0))))

        # P118 — fatigue_lifetime_index
        # heavy usage (mileage, maintenance history) -> higher fatigue
        p118 = _clamp01(0.5 * _clamp01(mileage_km / 200000.0) + 0.5 * _clamp01(p111))

        # P119 — human_reported_issue_index
        # map reported_issues 0..10 -> 0..1
        p119 = _clamp01(min(1.0, reported_issues / 10.0))

        # P120 — train_health_composite (final)
        # Weighted aggregate emphasizing brakes, wheels, maintenance and thermal stress
        p120_raw = (
            0.18 * p101 +
            0.15 * p102 +
            0.12 * p110 +
            0.10 * p111 +
            0.10 * p117 +
            0.08 * p115 +
            0.07 * p114 +
            0.06 * p108 +
            0.06 * p112 +
            0.08 * p119
        )
        p120 = _clamp01(p120_raw)

        results[tid] = {
            "p101": _clamp01(p101),
            "p102": _clamp01(p102),
            "p103": _clamp01(p103),
            "p104": _clamp01(p104),
            "p105": _clamp01(p105),
            "p106": _clamp01(p106),
            "p107": _clamp01(p107),
            "p108": _clamp01(p108),
            "p109": _clamp01(p109),
            "p110": _clamp01(p110),
            "p111": _clamp01(p111),
            "p112": _clamp01(p112),
            "p113": _clamp01(p113),
            "p114": _clamp01(p114),
            "p115": _clamp01(p115),
            "p116": _clamp01(p116),
            "p117": _clamp01(p117),
            "p118": _clamp01(p118),
            "p119": _clamp01(p119),
            "p120": _clamp01(p120)
        }

    return results
