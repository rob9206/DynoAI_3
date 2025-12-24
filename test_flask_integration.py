"""Test Flask integration of reliability agent"""
import sys
sys.path.insert(0, r'C:\Dev\DynoAI_3')

from flask import Flask
import traceback

app = Flask(__name__)

try:
    print("Attempting to initialize reliability agent...")
    from api.reliability_integration import init_reliability
    
    agent = init_reliability(app)
    print(f"[OK] Reliability agent initialized: {agent}")
    
    print("\nRegistered routes:")
    for rule in app.url_map.iter_rules():
        if 'reliability' in rule.rule:
            print(f"  {rule.methods} {rule.rule}")
    
    print("\n[SUCCESS] Flask integration working!")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nFull traceback:")
    traceback.print_exc()








