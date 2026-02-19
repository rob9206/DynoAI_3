"""Test reliability agent import and initialization"""
import sys
import traceback
import json

sys.path.insert(0, r'C:\Dev\DynoAI_3')

try:
    print("1. Testing import of reliability_agent...")
    from api.reliability_agent import get_reliability_agent
    print("   [OK] reliability_agent imported")
    
    print("\n2. Testing import of reliability_helpers...")
    from api.reliability_helpers import record_health
    print("   [OK] reliability_helpers imported")
    
    print("\n3. Testing import of reliability routes...")
    from api.routes.reliability import reliability_bp
    print("   [OK] reliability routes imported")
    
    print("\n4. Testing get_reliability_agent()...")
    agent = get_reliability_agent()
    print(f"   [OK] Agent created: {agent}")
    
    print("\n5. Testing get_system_health()...")
    health = agent.get_system_health()
    print(f"   [OK] Health data:")
    print(json.dumps(health, indent=2, default=str))
    
    print("\n[SUCCESS] All imports and basic functionality working!")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nFull traceback:")
    traceback.print_exc()

