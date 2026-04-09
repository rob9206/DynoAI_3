"""
COM-first automation orchestrator for MasterTune ingestion.

This script attempts to automate ingestion for many MT files:
1) Try COM extraction (if adapter is available)
2) Optional UI export hook command (user-provided)
3) Ingest TSV outputs via existing ingest script
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
GENERATE_TEMPLATES = SCRIPTS_DIR / "generate_mastertune_tsv_templates.py"
INGEST_TSV = SCRIPTS_DIR / "ingest_mastertune_tsv.py"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynoai.core.io_contracts import safe_path  # noqa: E402

DEFAULT_CAL_DIR = Path(r"C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations")
VALID_EXTENSIONS = {".mt7", ".mt8", ".mt9"}

FAILURE_TEMPLATE_GEN = "template_generation_failed"
FAILURE_UI_HOOK = "ui_hook_failed"
FAILURE_UI_HOOK_ABORT = "ui_hook_user_abort"
FAILURE_INGEST = "ingest_failed"
FAILURE_UNFILLED = "tsv_unfilled_after_hook"


def _scan_mt_files(root: Path, max_files: int = 0) -> List[Path]:
    files: List[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VALID_EXTENSIONS:
            continue
        files.append(path)
        if max_files > 0 and len(files) >= max_files:
            break
    return files


def _filter_by_contains(files: List[Path], patterns: List[str]) -> List[Path]:
    if not patterns:
        return files
    normalized = [p.lower() for p in patterns if p.strip()]
    if not normalized:
        return files
    out: List[Path] = []
    for file_path in files:
        name = file_path.name.lower()
        if any(pattern in name for pattern in normalized):
            out.append(file_path)
    return out


def _template_dir(mt_file: Path) -> Path:
    return mt_file.parent / "tsv_templates" / mt_file.stem


def _tsv_paths(mt_file: Path) -> Dict[str, Path]:
    base = _template_dir(mt_file)
    return {
        "dir": base,
        "ve_front": base / "ve_front_map.tsv",
        "ve_rear": base / "ve_rear_map.tsv",
        "lambda": base / "lambda_map.tsv",
    }


def _ensure_templates(mt_file: Path) -> None:
    cmd = [
        "python",
        str(GENERATE_TEMPLATES),
        "--mt-file",
        str(mt_file),
        "--output-dir",
        str(_template_dir(mt_file)),
    ]
    subprocess.run(cmd, check=True)


def _templates_exist(mt_file: Path) -> bool:
    tsv = _tsv_paths(mt_file)
    return all(tsv[key].exists() for key in ("ve_front", "ve_rear", "lambda"))


def _looks_filled(tsv_path: Path) -> bool:
    if not tsv_path.exists():
        return False
    lines = [line for line in tsv_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    tokens = set()
    for line in lines[1:]:
        for part in line.split("\t")[1:]:
            value = part.strip()
            if value:
                tokens.add(value)
    return len(tokens) > 6


def _ingest_from_tsv(mt_file: Path, library_dir: Optional[Path], notes: str) -> subprocess.CompletedProcess[str]:
    tsv = _tsv_paths(mt_file)
    cmd = [
        "python",
        str(INGEST_TSV),
        "--mt-file",
        str(mt_file),
        "--ve-front-tsv",
        str(tsv["ve_front"]),
        "--ve-rear-tsv",
        str(tsv["ve_rear"]),
        "--lambda-tsv",
        str(tsv["lambda"]),
        "--notes",
        notes or f"auto-ingest {mt_file.name}",
    ]
    if library_dir is not None:
        cmd.extend(["--library-dir", str(library_dir)])
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _run_ui_hook(
    command_template: str, mt_file: Path, template_dir: Path, axis_mode: str
) -> subprocess.CompletedProcess[str]:
    rendered = command_template.format(
        mt_file=str(mt_file),
        out_dir=str(template_dir),
        ve_front=str(template_dir / "ve_front_map.tsv"),
        ve_rear=str(template_dir / "ve_rear_map.tsv"),
        lambda_tsv=str(template_dir / "lambda_map.tsv"),
        axis_mode=axis_mode,
    )
    return subprocess.run(rendered, text=True, shell=True, check=False)


def _try_com_extract(_mt_file: Path) -> bool:
    """Placeholder for COM adapter extraction. Returns False until wired."""
    return False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate MasterTune ingest (COM-first)")
    parser.add_argument(
        "--calibration-dir",
        default=str(DEFAULT_CAL_DIR),
        help="Root directory containing .MT9/.MT8/.MT7 files",
    )
    parser.add_argument(
        "--library-dir",
        default=None,
        help="Calibration library output directory (optional)",
    )
    parser.add_argument("--max-files", type=int, default=0, help="Process at most N files")
    parser.add_argument(
        "--ui-export-cmd-template",
        default="",
        help=(
            "Shell command template for UI export hook. Placeholders: "
            "{mt_file}, {out_dir}, {ve_front}, {ve_rear}, {lambda_tsv}, {axis_mode}"
        ),
    )
    parser.add_argument(
        "--axis-mode",
        choices=["map", "tps", "auto"],
        default="auto",
        help="Preferred VE axis mode for UI export",
    )
    parser.add_argument(
        "--file-contains",
        action="append",
        default=[],
        help="Only process files whose name contains this text (repeatable)",
    )
    parser.add_argument("--notes", default="", help="Notes passed to ingest script")
    parser.add_argument(
        "--report-json",
        default=str(ROOT_DIR / "data" / "mastertune_catalog" / "auto_ingest_report.json"),
        help="Path to write automation report JSON",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already have filled TSV exports",
    )
    parser.add_argument(
        "--refresh-templates",
        action="store_true",
        help="Regenerate TSV templates even if files already exist",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop processing after first failure (default: continue)",
    )
    parser.add_argument(
        "--templates-only",
        action="store_true",
        help="Generate TSV templates for each file and exit (no UI hook, no ingest)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cal_dir = safe_path(args.calibration_dir, allow_parent_dir=True)
    library_dir = (
        safe_path(args.library_dir, allow_parent_dir=True)
        if args.library_dir
        else None
    )

    files = _scan_mt_files(cal_dir, max_files=0)
    files = _filter_by_contains(files, list(args.file_contains))
    if int(args.max_files) > 0:
        files = files[: int(args.max_files)]
    if not files:
        raise ValueError(f"No MT files found under {cal_dir}")

    summary: Dict[str, int] = {
        "total": len(files),
        "com_extracted": 0,
        "ui_hook_attempted": 0,
        "ingested": 0,
        "pending_manual": 0,
        "failed": 0,
        "skipped_existing": 0,
    }
    failure_reasons: Dict[str, int] = {}
    details: List[Dict[str, Any]] = []

    for file_idx, mt_file in enumerate(files, 1):
        status = "pending_manual"
        reason = ""
        message = ""
        tsv = _tsv_paths(mt_file)
        tsv_dir = tsv["dir"]
        tsv_dir.mkdir(parents=True, exist_ok=True)
        print("")
        print(f"[{file_idx}/{len(files)}] {mt_file.name}")

        try:
            if _try_com_extract(mt_file):
                summary["com_extracted"] += 1
                status = "com_extracted"

            if args.refresh_templates or not _templates_exist(mt_file):
                _ensure_templates(mt_file)
            else:
                print("  using existing TSV templates")
        except Exception as exc:
            status = "failed"
            reason = FAILURE_TEMPLATE_GEN
            message = str(exc)
            summary["failed"] += 1
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            details.append({"file": str(mt_file), "status": status, "reason": reason, "message": message})
            print(f"  FAILED ({reason}): {message}")
            if args.stop_on_error:
                break
            continue

        if args.templates_only:
            details.append({"file": str(mt_file), "status": "templates_generated", "reason": "", "message": ""})
            print("  templates ready")
            continue

        filled = _looks_filled(tsv["ve_front"]) and _looks_filled(tsv["lambda"])
        if filled and args.skip_existing:
            summary["skipped_existing"] += 1
            details.append({"file": str(mt_file), "status": "skipped_existing", "reason": "", "message": ""})
            print("  skipped (already filled)")
            continue

        if not filled and args.ui_export_cmd_template:
            summary["ui_hook_attempted"] += 1
            print("  launching UI export hook...")
            try:
                hook_result = _run_ui_hook(
                    args.ui_export_cmd_template, mt_file, tsv_dir, str(args.axis_mode)
                )
                if hook_result.returncode != 0:
                    is_abort = hook_result.returncode == 1
                    status = "failed"
                    reason = FAILURE_UI_HOOK_ABORT if is_abort else FAILURE_UI_HOOK
                    message = f"exit code {hook_result.returncode}"
                    summary["failed"] += 1
                    failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                    details.append({"file": str(mt_file), "status": status, "reason": reason, "message": message})
                    print(f"  FAILED ({reason}): {message}")
                    if args.stop_on_error:
                        break
                    continue
            except KeyboardInterrupt:
                print("\n  Interrupted by user. Saving report...")
                break
            filled = _looks_filled(tsv["ve_front"]) and _looks_filled(tsv["lambda"])

        if not filled:
            if not args.ui_export_cmd_template:
                reason = FAILURE_UNFILLED
                message = "no UI hook provided and TSVs empty"
            else:
                reason = FAILURE_UNFILLED
                message = "TSV files still empty after UI hook"
            summary["pending_manual"] += 1
            status = "pending_manual"
            details.append({"file": str(mt_file), "status": status, "reason": reason, "message": message})
            print(f"  pending manual ({message})")
            continue

        try:
            ingest_result = _ingest_from_tsv(mt_file, library_dir, args.notes)
            if ingest_result.returncode == 0:
                status = "ingested"
                message = ingest_result.stdout.strip()
                summary["ingested"] += 1
                print("  INGESTED")
            else:
                status = "failed"
                reason = FAILURE_INGEST
                message = ingest_result.stderr.strip() or ingest_result.stdout.strip()
                summary["failed"] += 1
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                print(f"  FAILED ({reason}): {message[:120]}")
        except Exception as exc:
            status = "failed"
            reason = FAILURE_INGEST
            message = f"{type(exc).__name__}: {exc}"
            summary["failed"] += 1
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            print(f"  FAILED ({reason}): {message[:120]}")

        details.append({"file": str(mt_file), "status": status, "reason": reason, "message": message})
        if status == "failed" and args.stop_on_error:
            break

    report_path = safe_path(args.report_json, allow_parent_dir=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": summary,
        "failure_reasons": failure_reasons,
        "details": details,
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("")
    print("=" * 50)
    print("Auto MasterTune ingest run complete")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    if failure_reasons:
        print("  failure breakdown:")
        for reason, count in sorted(failure_reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}")
    print(f"  report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
