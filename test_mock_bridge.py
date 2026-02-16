"""Quick test: start mock bridge, connect as client, check data flows."""
import socket, json, time
from api.services.simulation.dyno_simulator import (
    get_simulator, reset_simulator, SimulatorConfig, EngineProfile,
)

# 1. Start simulator
profile = EngineProfile.m8_114()
config = SimulatorConfig(profile=profile)
sim = reset_simulator(config)
sim.start()
time.sleep(0.3)

# 2. Start mock bridge
from api.routes.yourdyno.simulator import _MockTcpBridge
bridge = _MockTcpBridge()
bridge.start()
time.sleep(0.5)

# 3. Connect as a TCP client (like YourDynoClient would)
sock = socket.create_connection(("127.0.0.1", 9877), timeout=2)
sock.settimeout(3.0)
buf = b""
lines = []
try:
    for _ in range(20):
        data = sock.recv(65536)
        if not data:
            print("ERROR: Connection closed by bridge")
            break
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            lines.append(line.decode())
        if len(lines) >= 3:
            break
        time.sleep(0.15)
except socket.timeout:
    print("Timeout waiting for data, got", len(lines), "lines so far")

for i, line in enumerate(lines[:5]):
    parsed = json.loads(line)
    tp = parsed.get("type")
    if tp:
        print(f"  Line {i}: hello type={tp}")
    else:
        rpm = parsed.get("engine_rpm", "?")
        afr = parsed.get("afr_front", "?")
        print(f"  Line {i}: engine_rpm={rpm}, afr_front={afr}")

sock.close()
bridge.stop()
sim.stop()
print(f"TEST RESULT: {len(lines)} lines received ({'PASS' if len(lines) >= 2 else 'FAIL'})")
