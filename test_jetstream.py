#!/usr/bin/env python
"""Test if Jetstream routes are registered."""

import os
import sys
from pathlib import Path

# Set environment
os.environ["JETSTREAM_STUB_DATA"] = "true"
os.environ["JETSTREAM_ENABLED"] = "false"

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "api"))

print("[*] Testing Jetstream integration...")
print()

try:
    # Import the app
    from api.app import app
    
    print("[+] App imported successfully")
    print()
    
    # List all registered blueprints
    print("[*] Registered blueprints:")
    for bp_name, bp in app.blueprints.items():
        print(f"  - {bp_name}: {bp.url_prefix or '/'}")
    print()
    
    # List all routes
    print("[*] Registered routes (jetstream only):")
    for rule in app.url_map.iter_rules():
        if 'jetstream' in str(rule):
            print(f"  - {rule.methods}: {rule.rule}")
    print()
    
    if any('jetstream' in str(rule) for rule in app.url_map.iter_rules()):
        print("[+] SUCCESS: Jetstream routes are registered!")
    else:
        print("[-] ERROR: No Jetstream routes found!")
        
except Exception as e:
    print(f"[-] ERROR: {e}")
    import traceback
    traceback.print_exc()

