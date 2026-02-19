#!/usr/bin/env python
"""
Test script to verify that simulator pull data is used in analysis.

This test:
1. Starts the simulator
2. Triggers a pull
3. Waits for pull to complete
4. Analyzes using simulator_pull mode
5. Verifies the analysis used the actual pull data
"""

import time
import requests
import json

API_BASE = "http://localhost:5000/api/jetdrive"

def test_simulator_pull_analysis():
    """Test that simulator pull data is used in analysis."""
    
    print("=" * 60)
    print("Testing Simulator Pull Data Analysis")
    print("=" * 60)
    
    # 1. Start simulator
    print("\n1. Starting simulator...")
    response = requests.post(f"{API_BASE}/simulator/start", json={
        "profile": "m8_114",
        "auto_pull": False
    })
    
    if not response.ok:
        print(f"❌ Failed to start simulator: {response.text}")
        return False
    
    print("✅ Simulator started")
    time.sleep(1)
    
    # 2. Trigger a pull
    print("\n2. Triggering pull...")
    response = requests.post(f"{API_BASE}/simulator/pull")
    
    if not response.ok:
        print(f"❌ Failed to trigger pull: {response.text}")
        return False
    
    print("✅ Pull triggered")
    
    # 3. Wait for pull to complete (check state every 0.5s)
    print("\n3. Waiting for pull to complete...")
    max_wait = 20  # seconds
    start_time = time.time()
    pull_completed = False
    
    while time.time() - start_time < max_wait:
        response = requests.get(f"{API_BASE}/simulator/status")
        if response.ok:
            data = response.json()
            state = data.get("state", "")
            print(f"   State: {state}")
            
            if state in ["cooldown", "idle"]:
                pull_completed = True
                break
        
        time.sleep(0.5)
    
    if not pull_completed:
        print("❌ Pull did not complete in time")
        return False
    
    print("✅ Pull completed")
    
    # 4. Get pull data to verify it exists
    print("\n4. Checking pull data...")
    response = requests.get(f"{API_BASE}/simulator/pull-data")
    
    if not response.ok:
        print(f"❌ Failed to get pull data: {response.text}")
        return False
    
    pull_data = response.json()
    if not pull_data.get("has_data"):
        print("❌ No pull data available")
        return False
    
    points = pull_data.get("points", 0)
    peak_hp = pull_data.get("peak_hp", 0)
    peak_tq = pull_data.get("peak_tq", 0)
    
    print(f"✅ Pull data available: {points} points")
    print(f"   Peak HP: {peak_hp:.1f}")
    print(f"   Peak TQ: {peak_tq:.1f}")
    
    # 5. Run analysis using simulator_pull mode
    print("\n5. Running analysis with simulator_pull mode...")
    run_id = f"test_sim_pull_{int(time.time())}"
    
    response = requests.post(f"{API_BASE}/analyze", json={
        "run_id": run_id,
        "mode": "simulator_pull",
        "afr_targets": {
            "20": 14.7,
            "40": 14.0,
            "60": 13.5,
            "80": 12.8,
            "100": 12.5
        }
    })
    
    if not response.ok:
        print(f"❌ Analysis failed: {response.text}")
        return False
    
    result = response.json()
    
    if not result.get("success"):
        print(f"❌ Analysis unsuccessful: {result.get('error')}")
        return False
    
    print("✅ Analysis completed successfully")
    
    # 6. Verify analysis results match pull data
    analysis = result.get("analysis", {})
    analysis_hp = analysis.get("peak_hp", 0)
    analysis_tq = analysis.get("peak_tq", 0)
    
    print(f"\n6. Verifying analysis used pull data...")
    print(f"   Analysis HP: {analysis_hp:.1f}")
    print(f"   Analysis TQ: {analysis_tq:.1f}")
    
    # Allow for small differences due to processing
    hp_diff = abs(analysis_hp - peak_hp)
    tq_diff = abs(analysis_tq - peak_tq)
    
    if hp_diff > 5:  # Allow 5 HP difference
        print(f"❌ HP mismatch too large: {hp_diff:.1f} HP difference")
        print(f"   Expected ~{peak_hp:.1f}, got {analysis_hp:.1f}")
        return False
    
    if tq_diff > 5:  # Allow 5 ft-lb difference
        print(f"❌ Torque mismatch too large: {tq_diff:.1f} ft-lb difference")
        print(f"   Expected ~{peak_tq:.1f}, got {analysis_tq:.1f}")
        return False
    
    print(f"✅ Analysis results match pull data (within tolerance)")
    print(f"   HP difference: {hp_diff:.1f}")
    print(f"   TQ difference: {tq_diff:.1f}")
    
    # 7. Stop simulator
    print("\n7. Stopping simulator...")
    requests.post(f"{API_BASE}/simulator/stop")
    print("✅ Simulator stopped")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_simulator_pull_analysis()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

