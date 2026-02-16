"""End-to-end test: start simulator via API, check live data flows."""
import json
import time
import urllib.request

API = "http://127.0.0.1:5001/api/yourdyno"


def post(path, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{API}/{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return json.loads(urllib.request.urlopen(req).read())


def get(path):
    return json.loads(urllib.request.urlopen(f"{API}/{path}").read())


# 1. Start simulator
print("Starting simulator...")
result = post("simulator/start", {"profile": "m8_114"})
print(f"  -> {result.get('status')}")

# 2. Wait for data to flow
time.sleep(2)

# 3. Check live data
live = get("live/data")
print(f"  Channels: {live.get('channel_count')}")
print(f"  Status: {live.get('status')}")
print(f"  Error: {live.get('error')}")
if live.get("channels"):
    for k, v in sorted(live["channels"].items())[:6]:
        val = v.get("value", "?") if isinstance(v, dict) else v
        print(f"    {k}: {val}")

# 4. Check drain
drain = get("live/drain")
print(f"  Drain samples: {drain.get('count')}")

# 5. Stop
print("Stopping simulator...")
result = post("simulator/stop")
print(f"  -> {result.get('status')}")

success = live.get("channel_count", 0) > 0
print(f"\nRESULT: {'PASS' if success else 'FAIL'}")
