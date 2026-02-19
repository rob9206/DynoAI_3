
"""
Verification Script: Math Integration Bridge
============================================

Verifies that the V3 Session Service correctly:
1. Accepts raw AFR data (and optional targets)
2. Uses Core Math (`ve_math`) to calculate VE corrections
3. Ingests those corrections into the GP Surrogate

Simulates a +7.7% lean condition (14.0 AFR measured vs 13.0 target).
"""

import sys
import os
from pprint import pprint

# Add project root to path
sys.path.append(os.getcwd())

from api.services.v3_session_service import create_session, ingest_pull, _get_session
from dynoai.core.afr_targets import get_target_afr_for_map

def run_verification():
    print("=== DynoAI V3: Math Integration Verification ===\n")

    # 1. Create Session
    config = {
        "engine_family": "m8_114",
        "rpm_bins": [2000, 3000, 4000],
        "map_bins": [40, 60, 80]
    }
    session_data = create_session(config)
    session_id = session_data["session_id"]
    print(f"[OK] Session Created: {session_id}")

    # 2. Simulate Data
    # Scenario: Engine running lean (14.0) at a point where it should be rich (13.0)
    # Expected VE Correction: 14.0 / 13.0 = 1.0769 (+7.69%)
    
    rpm_point = 3000.0
    map_point = 80.0
    
    # Verify target lookup using our new module
    default_target = get_target_afr_for_map(map_point)
    print(f"Checking targets for {map_point}kPa: Default is {default_target}")
    
    # We will override with a specific target to make math easy to verify
    target_afr_val = 13.0
    measured_afr_val = 14.0
    base_ve_val = 80.0
    
    pull_data = {
        "rpm": [rpm_point],
        "map_kpa": [map_point],
        "afr": [measured_afr_val],
        "target_afr": [target_afr_val], # Optional, but providing for exact test
        "base_ve": [base_ve_val]
    }
    
    print(f"\nSimulating Pull:")
    print(f"  RPM: {rpm_point}")
    print(f"  MAP: {map_point} kPa")
    print(f"  AFR: {measured_afr_val} (Target: {target_afr_val})")
    print(f"  Base VE: {base_ve_val}%")
    
    # 3. Ingest (Should trigger math calculation)
    result = ingest_pull(session_id, **pull_data)
    print(f"[OK] Pull Ingested (Pull #{result['pull_number']})")
    print(f"  Observations Added: {result['observations_added']}")

    # 4. Inspect Surrogate
    session = _get_session(session_id)
    observations = session.surrogate.observations
    
    # Find our observation
    found = False
    for obs in observations:
        if obs.pull_number == result['pull_number']:
            found = True
            print(f"\nObservation Found in GP Surrogate:")
            print(f"  RPM: {obs.rpm}")
            print(f"  MAP: {obs.map_kpa}")
            print(f"  VE Absolute: {obs.ve_delta:.4f}%")
            
            # Verify Math
            expected_correction = measured_afr_val / target_afr_val
            # Absolute VE = Base * Correction
            expected_absolute_ve = base_ve_val * expected_correction
            
            error = abs(obs.ve_delta - expected_absolute_ve)
            
            print(f"  Expected Absolute VE: {expected_absolute_ve:.4f}%")
            
            if error < 0.01:
                print("\n[OK] SUCCESS: Calculated Absolute VE matches Core Math expectation!")
            else:
                print(f"\n[FAIL] FAILURE: Math mismatch (Error: {error:.4f})")
                
            break
            
    if not found:
        print("\n[FAIL] FAILURE: Observation not found in surrogate.")

    # -----------------------------------------------------------------------
    # 3. Verify Simulation Pipeline (simulate_pull_realistic)
    # -----------------------------------------------------------------------
    print("\n---------------------------------------------------")
    print("3. Verifying Simulation Pipeline (simulate_pull_realistic)")
    print("   Target: Ensure simulation uses the new AFR->Ingest path")
    print("---------------------------------------------------")

    # Access the service module directly since verification script imports it
    import api.services.v3_session_service as v3

    # Force a realistic simulation pull
    # We use a standard point (3000 RPM, 80 kPa)
    print("Running simulate_pull_realistic(3000, 80)...")
    sim_result = v3.simulate_pull_realistic(session_id, rpm=3000.0, map_kpa=80.0)
    
    print(f"Simulation Result: {sim_result}")
    
    if sim_result.get("mode") != "realistic":
        print("[WARN] Simulation fell back to 'quick' mode (simulator might need initialization). checks may vary.")
    
    obs_added = sim_result.get("observations_added", 0)
    print(f"Observations Added: {obs_added}")
    
    if obs_added > 0:
        print("[OK] Simulation successfully generated and ingested data.")
        
        # Verify the data stored in the surrogate
        # We expect Absolute VE values (approx 70-130 range), NOT deltas (-20 to +20).
        session = v3._get_session(session_id)
        if session.surrogate.observations:
             last_obs = session.surrogate.observations[-1]
             print(f"Last Observation stored: RPM={last_obs.rpm:.0f} MAP={last_obs.map_kpa:.0f} AbsVE={last_obs.ve_delta:.2f}%")
        
             if 50.0 < last_obs.ve_delta < 150.0:
                  print("[OK] SUCCESS: Surrogate contains Absolute VE values (Expected range 50-150%)")
             else:
                  print(f"[FAIL] Surrogate contains value {last_obs.ve_delta} which looks like a delta, not Absolute VE!")
        else:
             print("[FAIL] Surrogate observations list is empty despite obs_added > 0.")

    else:
        print("[FAIL] Realistic Simulation added 0 observations. Attempting Quick Mode fallback...")
        # Fallback to Quick Mode to verify *that* path
        quick_result = v3.simulate_pull(session_id, rpm=3500.0, map_kpa=80.0)
        print(f"Quick Mode Result: {quick_result}")
        if quick_result.get("observations_added", 0) > 0:
             print("[OK] Quick Mode successfully added observations.")
        else:
             print("[FAIL] Quick Mode also failed.")

    print("\n===================================================")
    print("VERIFICATION COMPLETE")
    print("===================================================")

if __name__ == "__main__":
    run_verification()
