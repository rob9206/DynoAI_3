from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_LOG_GLOB = r"C:\CommmandCenter\Customer_Files\seanbike\runnning_*.txt"


def _safe_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except Exception:
        return None


def _pick_col(header: list[str], preferred: list[str], contains: list[str]) -> int | None:
    for name in preferred:
        if name in header:
            return header.index(name)
    for i, col in enumerate(header):
        low = col.lower()
        if all(token in low for token in contains):
            return i
    return None


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    seq = sorted(values)
    pos = (len(seq) - 1) * p
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return seq[lo]
    w = pos - lo
    return seq[lo] * (1 - w) + seq[hi] * w


@dataclass
class PullCheckResult:
    path: Path
    parsed_rows: int
    rpm_max: float
    tps_max: float
    afr_p50: float
    afr_p90: float
    knock_max: float
    knock_over_2_count: int
    knock_over_1_count: int
    lean_over_50_count: int
    lean_over_70_count: int
    sustained_knock_consecutive_max: int
    verdict: str
    blockers: list[str]


def _read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="latin-1", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if not rows:
        raise ValueError(f"Empty file: {path}")
    header = [h.strip() for h in rows[0]]
    data_rows = [row for row in rows[1:] if len(row) == len(header)]
    return header, data_rows


def check_log(
    path: Path,
    knock_spike: float,
    knock_sustained: float,
    afr_limit_50: float,
    afr_limit_70: float,
    sustained_consecutive_min: int,
) -> PullCheckResult:
    header, rows = _read_rows(path)

    rpm_idx = _pick_col(
        header,
        preferred=[
            "(Harley - ECU Type 20 SW Level 357) Engine Speed",
            "(PV) Engine Speed",
            "(DWRT CPU) Engine RPM",
            "Engine Speed",
        ],
        contains=["engine", "speed"],
    )
    tps_idx = _pick_col(
        header,
        preferred=[
            "(Harley - ECU Type 20 SW Level 357) Throttle Position",
            "(PV) Throttle Position",
            "Throttle Position",
        ],
        contains=["throttle", "position"],
    )
    afr_idx = _pick_col(
        header,
        preferred=[
            "(DWRT CPU) LC2 Volts Petrol AFR2",
            "(DWRT CPU) LC1 Volts Petrol AFR",
        ],
        contains=["afr"],
    )
    kf_idx = _pick_col(
        header,
        preferred=[
            "(Harley - ECU Type 20 SW Level 357) Front Spark Knock Retard",
            "(PV) Front Spark Knock Retard",
            "Front Spark Knock Retard",
        ],
        contains=["front", "knock", "retard"],
    )
    kr_idx = _pick_col(
        header,
        preferred=[
            "(Harley - ECU Type 20 SW Level 357) Rear Spark Knock Retard",
            "(PV) Rear Spark Knock Retard",
            "Rear Spark Knock Retard",
        ],
        contains=["rear", "knock", "retard"],
    )

    if rpm_idx is None or tps_idx is None or afr_idx is None:
        missing = []
        if rpm_idx is None:
            missing.append("RPM")
        if tps_idx is None:
            missing.append("TPS")
        if afr_idx is None:
            missing.append("AFR")
        raise ValueError(f"{path.name}: missing required columns: {', '.join(missing)}")

    rpm_vals: list[float] = []
    tps_vals: list[float] = []
    afr_vals: list[float] = []
    knock_vals: list[float] = []
    lean_over_50_count = 0
    lean_over_70_count = 0
    knock_over_2_count = 0
    knock_over_1_count = 0
    sustained_knock_consecutive_max = 0
    current_streak = 0
    parsed_rows = 0

    for row in rows:
        rpm = _safe_float(row[rpm_idx])
        tps = _safe_float(row[tps_idx])
        afr = _safe_float(row[afr_idx])
        if rpm is None or tps is None or afr is None:
            continue
        if afr >= 22.38:  # LC-2 pegged/saturated - ignore for lean decisions
            continue
        parsed_rows += 1

        rpm_vals.append(rpm)
        tps_vals.append(tps)
        afr_vals.append(afr)

        kf = _safe_float(row[kf_idx]) if kf_idx is not None else None
        kr = _safe_float(row[kr_idx]) if kr_idx is not None else None
        kmax = max(v for v in [kf, kr] if v is not None) if (kf is not None or kr is not None) else 0.0
        knock_vals.append(kmax)

        if kmax >= knock_spike:
            knock_over_2_count += 1
        if kmax >= knock_sustained:
            knock_over_1_count += 1
            current_streak += 1
        else:
            sustained_knock_consecutive_max = max(sustained_knock_consecutive_max, current_streak)
            current_streak = 0

        if tps >= 50.0 and afr > afr_limit_50:
            lean_over_50_count += 1
        if tps >= 70.0 and afr > afr_limit_70:
            lean_over_70_count += 1

    sustained_knock_consecutive_max = max(sustained_knock_consecutive_max, current_streak)

    if not parsed_rows:
        return PullCheckResult(
            path=path,
            parsed_rows=0,
            rpm_max=0.0,
            tps_max=0.0,
            afr_p50=float("nan"),
            afr_p90=float("nan"),
            knock_max=0.0,
            knock_over_2_count=0,
            knock_over_1_count=0,
            lean_over_50_count=0,
            lean_over_70_count=0,
            sustained_knock_consecutive_max=0,
            verdict="ABORT",
            blockers=["No parseable rows after filtering (possibly AFR pegged or wrong channels)."],
        )

    # Convert RPM if logs are kRPM-scale
    rpm_scale = 1000.0 if max(rpm_vals) < 20 else 1.0
    rpm_max = max(rpm_vals) * rpm_scale
    tps_max = max(tps_vals)
    afr_p50 = _percentile(afr_vals, 0.50)
    afr_p90 = _percentile(afr_vals, 0.90)
    knock_max = max(knock_vals) if knock_vals else 0.0

    blockers: list[str] = []
    if knock_over_2_count > 0:
        blockers.append(f"Knock spike >= {knock_spike:.1f} deg seen ({knock_over_2_count} samples).")
    if sustained_knock_consecutive_max >= sustained_consecutive_min:
        blockers.append(
            f"Sustained knock >= {knock_sustained:.1f} deg for {sustained_knock_consecutive_max} consecutive samples."
        )
    if lean_over_50_count > 0:
        blockers.append(
            f"Lean over TPS>=50: AFR > {afr_limit_50:.1f} in {lean_over_50_count} samples."
        )
    if lean_over_70_count > 0:
        blockers.append(
            f"Lean over TPS>=70: AFR > {afr_limit_70:.1f} in {lean_over_70_count} samples."
        )

    verdict = "PASS" if not blockers else "ABORT"

    return PullCheckResult(
        path=path,
        parsed_rows=parsed_rows,
        rpm_max=rpm_max,
        tps_max=tps_max,
        afr_p50=afr_p50,
        afr_p90=afr_p90,
        knock_max=knock_max,
        knock_over_2_count=knock_over_2_count,
        knock_over_1_count=knock_over_1_count,
        lean_over_50_count=lean_over_50_count,
        lean_over_70_count=lean_over_70_count,
        sustained_knock_consecutive_max=sustained_knock_consecutive_max,
        verdict=verdict,
        blockers=blockers,
    )


def _iter_logs(patterns: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for pattern in patterns:
        path = Path(pattern)
        if any(ch in pattern for ch in "*?[]"):
            if path.is_absolute():
                out.extend(sorted(path.parent.glob(path.name)))
            else:
                out.extend(sorted(Path().glob(pattern)))
        elif path.exists():
            out.append(path)
    # unique preserve order
    seen = set()
    uniq = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check new dyno pull logs against first-flash abort thresholds."
    )
    parser.add_argument(
        "--logs",
        nargs="*",
        default=[DEFAULT_LOG_GLOB],
        help="Log paths/globs. Default: C:\\CommmandCenter\\Customer_Files\\seanbike\\runnning_*.txt",
    )
    parser.add_argument("--knock-spike", type=float, default=2.0)
    parser.add_argument("--knock-sustained", type=float, default=1.0)
    parser.add_argument("--sustained-consecutive-min", type=int, default=5)
    parser.add_argument("--afr-limit-50", type=float, default=13.5)
    parser.add_argument("--afr-limit-70", type=float, default=13.2)
    parser.add_argument("--latest", type=int, default=3, help="Only check N newest logs by mtime.")
    args = parser.parse_args()

    log_paths = _iter_logs(args.logs)
    if not log_paths:
        print("No logs matched.")
        return 1
    log_paths = sorted(log_paths, key=lambda p: p.stat().st_mtime, reverse=True)[: args.latest]
    log_paths = list(reversed(log_paths))  # print oldest->newest among selected

    overall_fail = False
    print("Post-pull protocol check")
    print(
        f"Thresholds: knock_spike>={args.knock_spike}, sustained>={args.knock_sustained} "
        f"for {args.sustained_consecutive_min} samples, AFR TPS>=50 > {args.afr_limit_50}, "
        f"AFR TPS>=70 > {args.afr_limit_70}"
    )
    print()

    for path in log_paths:
        try:
            result = check_log(
                path=path,
                knock_spike=args.knock_spike,
                knock_sustained=args.knock_sustained,
                afr_limit_50=args.afr_limit_50,
                afr_limit_70=args.afr_limit_70,
                sustained_consecutive_min=args.sustained_consecutive_min,
            )
        except Exception as exc:
            overall_fail = True
            print(f"{path.name}: ABORT")
            print(f"  ERROR: {exc}")
            print()
            continue

        if result.verdict != "PASS":
            overall_fail = True

        print(f"{result.path.name}: {result.verdict}")
        print(
            f"  rows={result.parsed_rows} rpm_max={result.rpm_max:.0f} "
            f"tps_max={result.tps_max:.1f} afr_p50={result.afr_p50:.2f} "
            f"afr_p90={result.afr_p90:.2f} knock_max={result.knock_max:.2f}"
        )
        if result.blockers:
            for blocker in result.blockers:
                print(f"  - {blocker}")
        print()

    if overall_fail:
        print("OVERALL: ABORT")
        return 2
    print("OVERALL: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
