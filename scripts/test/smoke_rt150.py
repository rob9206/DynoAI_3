#!/usr/bin/env python3
"""
RT-150 Smoke Test

Validates connect → start → stream → stop API sequence against the DynoAI server.

Usage:
    python scripts/smoke_rt150.py --base http://127.0.0.1:5001/api/jetdrive --seconds 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin


def _req(method: str, url: str, data: dict | None = None, timeout: float = 5.0) -> dict:
    req = urllib.request.Request(url, method=method.upper())
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    else:
        body = None
    try:
        with urllib.request.urlopen(req, data=body, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request failed: {e}") from e


def run_smoke(base: str, seconds: float = 5.0) -> int:
    print(f"[smoke] Base URL: {base}")

    # 1) Config
    cfg = _req("GET", urljoin(base + "/", "dyno/config"))
    if not cfg.get("success"):
        raise RuntimeError(f"dyno/config failed: {cfg}")
    print(f"[smoke] Dyno model: {cfg['config']['model']} serial={cfg['config']['serial_number']}")

    # 2) Connect
    connect = _req("POST", urljoin(base + "/", "hardware/connect"))
    if not connect.get("success"):
        raise RuntimeError(f"hardware/connect failed: {connect}")
    print(f"[smoke] Connected={connect['connected']} providers={connect.get('count', 0)}")

    # 3) Start live
    start = _req("POST", urljoin(base + "/", "hardware/start"))
    if start.get("status") not in {"started", "already_capturing"}:
        raise RuntimeError(f"hardware/start unexpected response: {start}")
    print(f"[smoke] Live: {start.get('status')}")

    # 4) Poll live data briefly
    t0 = time.time()
    seen = 0
    last_hp = None
    last_rpm = None
    while time.time() - t0 < seconds:
        data = _req("GET", urljoin(base + "/", "hardware/live/data"))
        if data.get("capturing"):
            channels = data.get("channels") or {}
            hp = channels.get("Horsepower", {}).get("value")
            rpm = (
                channels.get("Digital RPM 1", {}).get("value")
                or channels.get("RPM", {}).get("value")
            )
            last_hp = hp if hp is not None else last_hp
            last_rpm = rpm if rpm is not None else last_rpm
            seen += 1
        time.sleep(0.5)

    print(f"[smoke] Polls: {seen} last_rpm={last_rpm} last_hp={last_hp}")
    if seen == 0:
        raise RuntimeError("No live data samples observed")

    # 5) Stop live
    stop = _req("POST", urljoin(base + "/", "hardware/stop"))
    if stop.get("status") not in {"stopped"}:
        raise RuntimeError(f"hardware/stop unexpected response: {stop}")
    print("[smoke] Stopped")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5001/api/jetdrive", help="Base API URL")
    ap.add_argument("--seconds", type=float, default=5.0, help="Seconds to poll live data")
    args = ap.parse_args()
    try:
        return run_smoke(args.base, args.seconds)
    except Exception as exc:
        print(f"[smoke] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


