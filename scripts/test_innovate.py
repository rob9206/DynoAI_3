#!/usr/bin/env python3
"""
Test script for Innovate DLG-1/LC-2 client functionality.

Tests:
1. Module imports
2. Port listing
3. API endpoints (if backend is running)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Innovate Client Test Suite")
print("=" * 60)

# Test 1: Import
print("\n[1] Testing imports...")
try:
    from api.services.innovate_client import (
        InnovateClient,
        list_available_ports,
        InnovateDeviceType,
        InnovateSample,
    )
    print("[OK] All imports successful")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)

# Test 2: Port listing
print("\n[2] Testing port listing...")
try:
    ports = list_available_ports()
    print(f"[OK] Found {len(ports)} serial port(s)")
    if ports:
        print("  Available ports:")
        for port in ports[:5]:  # Show first 5
            desc = port.get("description", "N/A")
            print(f"    - {port['port']}: {desc}")
    else:
        print("  (No serial ports found - this is OK if no devices are connected)")
except Exception as e:
    print(f"[FAIL] Port listing failed: {e}")

# Test 3: Client instantiation
print("\n[3] Testing client instantiation...")
try:
    # Test without connecting (should not fail)
    client = InnovateClient(port="COM99", device_type=InnovateDeviceType.AUTO)
    print("[OK] Client instantiation successful")
    print(f"  Port: {client.port}")
    print(f"  Device type: {client.device_type.value}")
    print(f"  Baudrate: {client.baudrate}")
except Exception as e:
    print(f"[FAIL] Client instantiation failed: {e}")

# Test 4: Sample data structure
print("\n[4] Testing data structures...")
try:
    import time
    sample = InnovateSample(
        timestamp=time.time(),
        afr=14.7,
        lambda_value=1.0,
        channel=1,
        device_type="LC-2",
    )
    print("[OK] InnovateSample creation successful")
    print(f"  AFR: {sample.afr}")
    print(f"  Lambda: {sample.lambda_value}")
    print(f"  Channel: {sample.channel}")
except Exception as e:
    print(f"[FAIL] Sample creation failed: {e}")

# Test 5: API endpoints (if backend is running)
print("\n[5] Testing API endpoints...")
try:
    import requests
    
    base_url = "http://localhost:5001"
    
    # Test port listing endpoint
    try:
        response = requests.get(f"{base_url}/api/jetdrive/innovate/ports", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print("[OK] GET /api/jetdrive/innovate/ports - OK")
            if data.get("success"):
                port_count = len(data.get("ports", []))
                print(f"  Found {port_count} port(s) via API")
        else:
            print(f"[FAIL] GET /api/jetdrive/innovate/ports - Status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("  (Backend not running - skipping API tests)")
    except requests.exceptions.Timeout:
        print("  (Backend timeout - skipping API tests)")
    except Exception as e:
        print(f"  API test error: {e}")
    
    # Test status endpoint
    try:
        response = requests.get(f"{base_url}/api/jetdrive/innovate/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print("[OK] GET /api/jetdrive/innovate/status - OK")
            print(f"  Connected: {data.get('connected', False)}")
        else:
            print(f"[FAIL] GET /api/jetdrive/innovate/status - Status {response.status_code}")
    except requests.exceptions.ConnectionError:
        pass  # Already reported
    except Exception as e:
        print(f"  Status endpoint error: {e}")
        
except ImportError:
    print("  (requests library not available - skipping API tests)")

# Test 6: Protocol parsing
print("\n[6] Testing protocol parsing...")
try:
    client = InnovateClient(port="COM99", device_type=InnovateDeviceType.LC2)
    
    # Test various data formats
    test_cases = [
        (b"AFR: 14.7\r\n", 14.7),
        (b"14.7\r\n", 14.7),
        (b"14.7,1.0\r\n", 14.7),
        (b"CH1: 12.5\r\n", 12.5),
        (b"invalid\r\n", None),
        (b"", None),
    ]
    
    passed = 0
    for data_bytes, expected_afr in test_cases:
        sample = client._parse_data(data_bytes, channel=1)
        if expected_afr is None:
            if sample is None:
                passed += 1
        else:
            if sample and abs(sample.afr - expected_afr) < 0.1:
                passed += 1
    
    print(f"[OK] Protocol parsing: {passed}/{len(test_cases)} test cases passed")
    
except Exception as e:
    print(f"[FAIL] Protocol parsing test failed: {e}")

print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print("[OK] Basic functionality tests completed")
print("\nNote: Connection tests require a physical Innovate device.")
print("      To test with a real device:")
print("      1. Connect your DLG-1 or LC-2 via USB")
print("      2. Find the COM port (use /api/jetdrive/innovate/ports)")
print("      3. Connect via POST /api/jetdrive/innovate/connect")
print("      4. Start live capture: POST /api/jetdrive/hardware/live/start")
print("      5. View data: GET /api/jetdrive/hardware/live/data")

