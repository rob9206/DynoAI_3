# experiments/agent_explore.py
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "experiments" / "run_experiment.py"
IDEAS_FILE = ROOT / "experiments" / "ideas.yaml"


def safe_within_root(path: Path) -> Path:
    p = path.resolve()
    root = ROOT.resolve()
    if root not in p.parents and p != root:
        raise ValueError(f"Refusing to write outside project root: {p}")
    return p


essential_outputs = [
    "manifest.json",
    "VE_Correction_Delta_DYNO.csv",
    "experiment_summary.json",
]


def load_manifest_metrics(manifest_path: Path) -> Dict[str, Any]:
    try:
        m = cast(Dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    except Exception:
        return {"status": "missing"}
    raw_stats = m.get("stats")
    stats: Dict[str, Any] = cast(Dict[str, Any], raw_stats) if isinstance(raw_stats, dict) else {}
    raw_status = m.get("status")
    status_block: Dict[str, Any] = cast(Dict[str, Any], raw_status) if isinstance(raw_status, dict) else {}
    raw_apply = m.get("apply")
    apply_block: Dict[str, Any] = cast(Dict[str, Any], raw_apply) if isinstance(raw_apply, dict) else {}
    status = status_block.get("code")
    apply_allowed = apply_block.get("allowed")
    return {
        "status": status,
        "apply_allowed": bool(apply_allowed) if isinstance(apply_allowed, (bool, int)) else None,
        "bins_total": stats.get("bins_total"),
        "bins_covered": stats.get("bins_covered"),
        "rows_read": stats.get("rows_read"),
    }


def run_runner(
    idea_id: str,
    csv_path: Path,
    outdir: Path,
    smooth_passes: int,
    clamp: float,
    rear_bias: float,
    rear_rule_deg: float,
    hot_extra: float,
    baseline: bool,
) -> Tuple[int, Dict[str, Any]]:
    cmd = [
        sys.executable,
        str(RUNNER),
        "--idea-id",
        idea_id,
        "--csv",
        str(csv_path),
        "--outdir",
        str(outdir),
        "--smooth_passes",
        str(smooth_passes),
        "--clamp",
        str(clamp),
        "--rear_bias",
        str(rear_bias),
        "--rear_rule_deg",
        str(rear_rule_deg),
        "--hot_extra",
        str(hot_extra),
    ]
    if baseline:
        cmd.append("--baseline")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    # Collect minimal metrics for orchestration
    summary_path = outdir / "experiment_summary.json"
    manifest_path = outdir / "manifest.json"
    summary: Dict[str, Any] = {}
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summary = {}
    metrics = load_manifest_metrics(manifest_path)
    if summary:
        metrics.update(summary.get("metrics", {}))
        if "avg_abs_ve_delta_vs_baseline" in summary:
            metrics["avg_abs_ve_delta_vs_baseline"] = summary["avg_abs_ve_delta_vs_baseline"]
        metrics["duration_sec"] = summary.get("duration_sec")
        metrics["idea_id"] = summary.get("idea_id", idea_id)
    else:
        metrics["idea_id"] = idea_id
    return proc.returncode or 0, metrics


def parse_ideas(path: Path) -> List[str]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        data = loaded if isinstance(loaded, dict) else {}
        raw_ideas = data.get("ideas", [])
        ideas = [i for i in raw_ideas if isinstance(i, dict)]
        # Only accept IDs that are already strings (not integers or other types)
        ids = [i.get("id") for i in ideas if isinstance(i.get("id"), str)]
        # Keep unique and stable order
        seen: set[str] = set()
        out: List[str] = []
        for s in ids:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out
    except Exception:
        # Fallback: two known prototypes if YAML missing
        return ["adaptive-kernel-v1", "edge-preserve-v1"]


def write_report(outdir: Path, rows: List[Dict[str, Any]], baseline_cov: float | None) -> None:
    report_path = outdir / "REPORT.md"
    lines: List[str] = []
    lines.append("# Experiment Report\n")
    lines.append("")
    if baseline_cov is not None:
        lines.append(f"Baseline coverage: {baseline_cov:.1f}%\n")
    lines.append("| Idea | Status | Apply | Coverage % | ΔCoverage | Avg | Duration (s) |\n")
    lines.append("|---|---|---|---:|---:|---:|---:|\n")
    for r in rows:
        cov = r.get("coverage_pct")
        dcov = r.get("coverage_drop_pct")
        cov_s = f"{cov:.1f}%" if isinstance(cov, float) else "-"
        d_s = f"-{dcov:.1f}%" if isinstance(dcov, float) else "-"
        avg = r.get("avg_abs_ve_delta_vs_baseline")
        avg_s = f"{avg:.3f}" if isinstance(avg, (int, float)) else "-"
        lines.append(
            f"| {r.get('idea_id','?')} | {r.get('status','?')} | {r.get('apply_allowed')} | {cov_s} | {d_s} | {avg_s} | {r.get('duration_sec','-')} |"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run baseline and all ideas, aggregate metrics and report")
    ap.add_argument("--csv", required=True, help="Input dyno CSV / WinPEP file")
    ap.add_argument(
        "--outdir",
        required=True,
        help="Output root directory for the exploration run (will contain baseline/ and one subfolder per idea)",
    )
    ap.add_argument("--ideas", default=str(IDEAS_FILE), help="Path to ideas.yaml")
    ap.add_argument("--smooth_passes", type=int, default=2)
    ap.add_argument("--clamp", type=float, default=15.0)
    ap.add_argument("--rear_bias", type=float, default=0.0)
    ap.add_argument("--rear_rule_deg", type=float, default=2.0)
    ap.add_argument("--hot_extra", type=float, default=-1.0)
    args = ap.parse_args()

    csv_path = Path(args.csv).resolve()
    outroot = safe_within_root(Path(args.outdir))
    outroot.mkdir(parents=True, exist_ok=True)

    # 1) Baseline
    baseline_dir = outroot / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    _code, base_metrics = run_runner(
        idea_id="baseline",
        csv_path=csv_path,
        outdir=baseline_dir,
        smooth_passes=args.smooth_passes,
        clamp=args.clamp,
        rear_bias=args.rear_bias,
        rear_rule_deg=args.rear_rule_deg,
        hot_extra=args.hot_extra,
        baseline=True,
    )
    base_bins_total = base_metrics.get("bins_total") or 0
    base_bins_cov = base_metrics.get("bins_covered") or 0
    baseline_cov = (100.0 * base_bins_cov / base_bins_total) if base_bins_total else None

    # 2) Ideas
    idea_ids = parse_ideas(Path(args.ideas))
    rows: List[Dict[str, Any]] = []
    for idea_id in idea_ids:
        idea_dir = outroot / idea_id
        idea_dir.mkdir(parents=True, exist_ok=True)
        _code, metrics = run_runner(
            idea_id=idea_id,
            csv_path=csv_path,
            outdir=idea_dir,
            smooth_passes=args.smooth_passes,
            clamp=args.clamp,
            rear_bias=args.rear_bias,
            rear_rule_deg=args.rear_rule_deg,
            hot_extra=args.hot_extra,
            baseline=False,
        )
        bins_total = metrics.get("bins_total") or 0
        bins_cov = metrics.get("bins_covered") or 0
        cov_pct = (100.0 * bins_cov / bins_total) if bins_total else None
        drop_pct = None
        if baseline_cov is not None and cov_pct is not None:
            drop_pct = max(0.0, baseline_cov - cov_pct)
        flagged = bool(drop_pct is not None and drop_pct > 10.0)
        metrics["coverage_pct"] = cov_pct
        metrics["coverage_drop_pct"] = drop_pct
        metrics["coverage_drop_flagged"] = flagged
        rows.append(metrics)

    # 3) Report
    agg_path = outroot / "aggregate.json"
    agg: Dict[str, Any] = {
        "baseline": base_metrics,
        "ideas": rows,
    }
    agg_path.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    write_report(outroot, rows, baseline_cov)

    print(json.dumps({
        "baseline_cov_pct": baseline_cov,
        "ideas": [
            {
                "idea_id": r.get("idea_id"),
                "avg_abs_ve_delta_vs_baseline": r.get("avg_abs_ve_delta_vs_baseline"),
                "coverage_drop_pct": r.get("coverage_drop_pct"),
                "flagged": r.get("coverage_drop_flagged"),
            }
            for r in rows
        ]
    }, indent=2))


if __name__ == "__main__":
    main()
