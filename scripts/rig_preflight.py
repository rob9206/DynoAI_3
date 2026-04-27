"""Tier 5 rig pre-flight verifier.

Run this on the rig laptop AFTER starting the API but BEFORE creating a
real workspace session. It checks the things that are tedious to verify
manually:

  - API server reachable and Tuning Workspace blueprint registered
  - JetDrive multicast discovery returns at least one provider
  - Active wideband calibration matches expectations
  - DYNOAI_WORKSPACE_ROOT is set to a real, writable path
  - Optional: live capture for ~10 seconds and verify AFR channels
    canonicalize correctly (no 0-5V values in AFR slots)

Usage:
    python scripts/rig_preflight.py [--api http://localhost:5001] [--live]

Exits 0 on success, 1 on any check failure. Designed to be safe to run on
a real rig: makes only GET / start / stop calls, never creates a vehicle
or modifies the ECM.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# Allow this script to be run from anywhere (e.g. on a rig laptop where the
# user is in `C:\Users\tuner` not the repo root). We import internal modules
# (wideband_rescale) for the calibration check, which requires the repo root
# on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    fix_hint: str = ""


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, c: CheckResult) -> None:
        self.checks.append(c)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def render(self) -> str:
        out: list[str] = []
        for c in self.checks:
            mark = "PASS" if c.passed else "FAIL"
            out.append(f"  [{mark}] {c.name}")
            if c.detail:
                out.append(f"          {c.detail}")
            if not c.passed and c.fix_hint:
                out.append(f"          fix: {c.fix_hint}")
        out.append("")
        out.append("OVERALL: " + ("PASS" if self.passed else "FAIL"))
        return "\n".join(out)


def _validate_local_url(url: str) -> str:
    """Reject URLs that aren't HTTP/HTTPS to a local-only host.

    This is a CLI tool, so `url` comes from `--api` and is operator-controlled,
    not attacker-controlled. The validation is belt-and-suspenders: it
    prevents misuse (e.g. someone wrapping this script in a web frontend)
    and silences SSRF static-analysis warnings cleanly.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"only http/https URLs allowed, got scheme={parsed.scheme!r}")
    host = parsed.hostname or ""
    # Allow common loopback/local-network forms only. The rig laptop talks
    # to its own DynoAI API on localhost or LAN; never to public hosts.
    if host in {"localhost", "127.0.0.1", "::1"}:
        return url
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
        return url
    raise ValueError(
        f"--api host {host!r} is not local; preflight only talks to local APIs"
    )


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, dict]:
    safe_url = _validate_local_url(url)
    req = urllib.request.Request(safe_url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- validated above
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return resp.status, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return resp.status, {"raw": body[:500]}


def _http_post(url: str, payload: dict | None = None, timeout: float = 5.0) -> tuple[int, dict]:
    safe_url = _validate_local_url(url)
    body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        safe_url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- validated above
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return resp.status, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return resp.status, {"raw": body[:500]}


def check_api_reachable(api: str, report: PreflightReport) -> None:
    try:
        status, data = _http_get(f"{api}/api/health")
        if status == 200 and data.get("status") in {"healthy", "degraded"}:
            report.add(CheckResult(
                name="API reachable",
                passed=True,
                detail=f"version={data.get('version', '?')} status={data.get('status')}",
            ))
        else:
            report.add(CheckResult(
                name="API reachable",
                passed=False,
                detail=f"status={status} body={data}",
                fix_hint=(
                    "Start the API: python -m flask --app api.app run "
                    "--host 0.0.0.0 --port 5001 --no-reload"
                ),
            ))
    except (urllib.error.URLError, OSError) as exc:
        report.add(CheckResult(
            name="API reachable",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
            fix_hint=f"Confirm the API process is running and listening at {api}",
        ))


def check_workspace_blueprint(api: str, report: PreflightReport) -> None:
    try:
        status, data = _http_get(f"{api}/api/workspace/vehicles")
        if status == 200 and isinstance(data, list):
            report.add(CheckResult(
                name="Workspace blueprint registered",
                passed=True,
                detail=f"vehicles_known={len(data)}",
            ))
        else:
            report.add(CheckResult(
                name="Workspace blueprint registered",
                passed=False,
                detail=f"status={status} body={data}",
                fix_hint=(
                    "On startup the API should print "
                    "'[+] Tuning Workspace registered at /api/workspace'. "
                    "If it didn't, check the import error in the server log."
                ),
            ))
    except urllib.error.HTTPError as exc:
        report.add(CheckResult(
            name="Workspace blueprint registered",
            passed=False,
            detail=f"HTTP {exc.code}: {exc.reason}",
            fix_hint="Workspace blueprint is missing; check api/app.py registration.",
        ))


def check_jetdrive_discovery(api: str, report: PreflightReport, timeout: float = 5.0) -> None:
    try:
        url = f"{api}/api/jetdrive/hardware/discover?timeout={timeout}"
        status, data = _http_get(url, timeout=timeout + 5.0)
    except (urllib.error.URLError, OSError) as exc:
        report.add(CheckResult(
            name="JetDrive multicast discovery",
            passed=False,
            detail=f"request failed: {exc}",
            fix_hint=(
                "Check JETDRIVE_IFACE env var is set to the right NIC IP. "
                "Confirm laptop and DynoWare are on the same subnet."
            ),
        ))
        return

    if status != 200 or not data.get("success"):
        report.add(CheckResult(
            name="JetDrive multicast discovery",
            passed=False,
            detail=f"status={status} body={data}",
        ))
        return

    found = data.get("providers_found", 0)
    providers = data.get("providers", [])
    if found == 0:
        report.add(CheckResult(
            name="JetDrive multicast discovery",
            passed=False,
            detail="0 providers found",
            fix_hint=(
                "Confirm DynoWare RT-150 is powered on and has a link light. "
                "Check that the laptop NIC is on the same VLAN. Try "
                "JETDRIVE_MCAST_GROUP=239.255.60.60 if using legacy multicast."
            ),
        ))
        return

    summary = ", ".join(
        f"{p.get('name', 'unknown')}@{p.get('host', '?')} ({len(p.get('channels', []))} ch)"
        for p in providers
    )
    report.add(CheckResult(
        name="JetDrive multicast discovery",
        passed=True,
        detail=f"providers_found={found}: {summary}",
    ))


def check_wideband_calibration(report: PreflightReport) -> None:
    try:
        from api.services.jetdrive.wideband_rescale import get_active_calibration
    except ImportError as exc:
        report.add(CheckResult(
            name="Wideband calibration loaded",
            passed=False,
            detail=f"cannot import wideband_rescale: {exc}",
            fix_hint="api/services/jetdrive/wideband_rescale.py missing or broken.",
        ))
        return

    cal = get_active_calibration()
    detail = (
        f"name={cal.name!r} v={cal.v_min}-{cal.v_max} -> AFR={cal.afr_min}-{cal.afr_max}"
    )
    # Sanity check: slope must be plausible (Innovate LC-2 default ~3.008,
    # custom values should still be in [1, 10]).
    if not (1.0 <= cal.slope <= 10.0):
        report.add(CheckResult(
            name="Wideband calibration loaded",
            passed=False,
            detail=detail + f" (slope={cal.slope:.3f} out of range)",
            fix_hint=(
                "DYNOAI_WIDEBAND_V_MIN/MAX/AFR_MIN/AFR_MAX env vars look wrong. "
                "Default LC-2 petrol: 0/5/7.35/22.39."
            ),
        ))
        return
    report.add(CheckResult(
        name="Wideband calibration loaded",
        passed=True,
        detail=detail,
    ))


def check_workspace_root(report: PreflightReport) -> None:
    root = os.environ.get("DYNOAI_WORKSPACE_ROOT", "vehicles")
    abs_root = os.path.abspath(root)
    if not os.path.isdir(abs_root):
        report.add(CheckResult(
            name="DYNOAI_WORKSPACE_ROOT exists",
            passed=False,
            detail=f"{abs_root}: directory does not exist",
            fix_hint=(
                "Workspace will create it lazily on first use, but for a rig "
                "test you should pre-create it: "
                f"mkdir -p {abs_root}"
            ),
        ))
        return
    if not os.access(abs_root, os.W_OK):
        report.add(CheckResult(
            name="DYNOAI_WORKSPACE_ROOT writable",
            passed=False,
            detail=f"{abs_root}: not writable",
            fix_hint="Check filesystem permissions on the workspace directory.",
        ))
        return
    report.add(CheckResult(
        name="DYNOAI_WORKSPACE_ROOT writable",
        passed=True,
        detail=abs_root,
    ))


def check_live_canonicalization(api: str, report: PreflightReport, capture_seconds: float = 10.0) -> None:
    """OPT-IN: start live capture, look at AFR channels, stop.

    Triggered with --live. Will not fire pulls or change ECM state.
    """
    try:
        status, _ = _http_post(f"{api}/api/jetdrive/hardware/start")
        if status != 200:
            report.add(CheckResult(
                name="Live capture starts",
                passed=False,
                detail=f"start returned status={status}",
            ))
            return
    except (urllib.error.URLError, OSError) as exc:
        report.add(CheckResult(
            name="Live capture starts",
            passed=False,
            detail=f"start failed: {exc}",
        ))
        return

    time.sleep(capture_seconds)

    try:
        status, data = _http_get(f"{api}/api/jetdrive/hardware/live/data")
    except Exception as exc:
        _http_post(f"{api}/api/jetdrive/hardware/stop")
        report.add(CheckResult(
            name="Live capture starts",
            passed=False,
            detail=f"read failed: {exc}",
        ))
        return

    _http_post(f"{api}/api/jetdrive/hardware/stop")

    channels = data.get("channels", {})
    if not channels:
        report.add(CheckResult(
            name="Live data populated",
            passed=False,
            detail="no channels received during 10s capture window",
            fix_hint=(
                "Provider visible to discover but emitting no values. "
                "Check Power Core is showing live data on its scope."
            ),
        ))
        return

    afr_channels = {}
    for name, ch in channels.items():
        n = name.lower()
        if (
            "afr" in n
            or "air/fuel" in n
            or "a/f" in n
            or "lambda" in n
            or "wbo2" in n
            or "wideband" in n
        ):
            afr_channels[name] = ch.get("value")
    if not afr_channels:
        report.add(CheckResult(
            name="AFR channels canonicalized",
            passed=False,
            detail="no AFR/lambda channels found in live data",
            fix_hint=(
                "Provider may not include wideband. If using LC-2 via voltage, "
                "check the channel name in DynoWare matches "
                "match_wideband_channel() in wideband_rescale.py."
            ),
        ))
        return

    suspect: list[str] = []
    canonicalized = []
    for name, value in afr_channels.items():
        if value is None:
            continue
        if isinstance(value, (int, float)):
            if 0 <= value <= 5.5:
                # AFR values in the 0-5 range are almost certainly raw volts
                # that didn't get rescaled. Real AFR is 8-25.
                suspect.append(f"{name}={value:.3f}")
            else:
                canonicalized.append(f"{name}={value:.2f}")

    if suspect:
        report.add(CheckResult(
            name="AFR channels canonicalized",
            passed=False,
            detail="suspect raw-voltage values: " + ", ".join(suspect),
            fix_hint=(
                "wideband_rescale didn't fire on these channels. Either the "
                "channel name doesn't match (extend match_wideband_channel) "
                "or the active calibration is wrong (set DYNOAI_WIDEBAND_* "
                "env vars)."
            ),
        ))
    else:
        report.add(CheckResult(
            name="AFR channels canonicalized",
            passed=True,
            detail=", ".join(canonicalized) if canonicalized else "none seen",
        ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default="http://localhost:5001",
        help="API base URL (default: http://localhost:5001)",
    )
    parser.add_argument(
        "--discover-timeout",
        type=float,
        default=5.0,
        help="JetDrive discovery timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also start a 10s live capture and verify AFR canonicalization. "
             "Safe: stops automatically. Skips by default to keep the script "
             "side-effect free.",
    )
    args = parser.parse_args(argv)

    report = PreflightReport()
    print("Tier 5 rig pre-flight checks")
    print(f"  API: {args.api}")
    print(f"  WORKSPACE_ROOT: {os.environ.get('DYNOAI_WORKSPACE_ROOT', '<unset, defaults to ./vehicles>')}")
    print()

    check_api_reachable(args.api, report)
    if not report.checks[-1].passed:
        # No point running anything else if the API is down.
        print(report.render())
        return 1

    check_workspace_blueprint(args.api, report)
    check_workspace_root(report)
    check_wideband_calibration(report)
    check_jetdrive_discovery(args.api, report, timeout=args.discover_timeout)

    if args.live:
        check_live_canonicalization(args.api, report)

    print(report.render())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
