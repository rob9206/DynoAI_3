"""
Export MasterTune tables to TSV files (UI-assisted).

This helper is designed for use with auto_mastertune_ingest.py via
--ui-export-cmd-template.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynoai.core.io_contracts import safe_path  # noqa: E402
from api.services.external_scrapers.mastertune_parser import (  # noqa: E402
    parse_tsv_grid_text,
    parse_tsv_grid_file,
    parse_values_only_matrix,
)


def _read_clipboard_text() -> str:
    import tkinter  # stdlib

    root = tkinter.Tk()
    root.withdraw()
    try:
        text = root.clipboard_get()
    except tkinter.TclError:
        text = ""
    finally:
        root.destroy()
    if text.strip():
        return text

    if os.name == "nt":
        try:
            probe = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                check=False,
                capture_output=True,
                text=True,
            )
            fallback = probe.stdout or ""
            if fallback.strip():
                return fallback
        except Exception:
            pass
    return text


def _linspace(start: float, end: float, count: int) -> List[float]:
    if count <= 0:
        return []
    if count == 1:
        return [float(start)]
    step = (float(end) - float(start)) / float(count - 1)
    return [round(float(start) + (step * float(idx)), 2) for idx in range(count)]


def _normalize_clipboard_to_tsv(
    text: str, template_path: Path, table_label: str
) -> Optional[str]:
    """
    Attempt to convert clipboard text into a valid headered TSV.

    Tries, in order:
    1. Direct parse as headered TSV (already has RPM + bins).
    2. Values-only matrix aligned to template bins (exact or stripped labels).
    3. Values-only matrix with synthesized axis bins from template range.

    Returns the TSV string on success, or None if all strategies fail.
    """
    # Strategy 1: direct headered parse
    try:
        parse_tsv_grid_text(text, source_name="clipboard")
        return text
    except Exception:
        pass

    template = parse_tsv_grid_file(template_path)
    target_rows = len(template.row_bins)
    target_cols = len(template.col_bins)

    matrix = parse_values_only_matrix(text, source_name="clipboard")
    if matrix is None:
        return None

    actual_rows = len(matrix)
    actual_cols = len(matrix[0]) if matrix else 0

    # Strategy 2a: exact match
    if actual_rows == target_rows and actual_cols == target_cols:
        return _build_tsv(template.row_bins, template.col_bins, matrix)

    # Strategy 2b: row-label matrix (RPM in col 0)
    if actual_rows == target_rows and actual_cols == target_cols + 1:
        stripped = [row[1:] for row in matrix]
        return _build_tsv(template.row_bins, template.col_bins, stripped)

    # Strategy 2c: col-label matrix (MAP bins in row 0)
    if actual_rows == target_rows + 1 and actual_cols == target_cols:
        stripped = matrix[1:]
        return _build_tsv(template.row_bins, template.col_bins, stripped)

    # Strategy 2d: both labels present
    if actual_rows == target_rows + 1 and actual_cols == target_cols + 1:
        stripped = [row[1:] for row in matrix[1:]]
        return _build_tsv(template.row_bins, template.col_bins, stripped)

    # Strategy 3: synthesize bins from template range for arbitrary dimensions
    row_bins = _linspace(template.row_bins[0], template.row_bins[-1], actual_rows)
    col_bins = _linspace(template.col_bins[0], template.col_bins[-1], actual_cols)
    return _build_tsv(row_bins, col_bins, matrix)


def _build_tsv(
    row_bins: List[float], col_bins: List[float], matrix: List[List[float]]
) -> str:
    header = ["RPM"] + [str(v) for v in col_bins]
    out_lines = ["\t".join(header)]
    for rpm, row in zip(row_bins, matrix):
        out_lines.append("\t".join([str(rpm)] + [str(v) for v in row]))
    return "\n".join(out_lines) + "\n"


def _launch_mt(mt_file: Path) -> None:
    if os.name == "nt":
        os.startfile(str(mt_file))
        return
    raise RuntimeError("Automatic launch only supported on Windows")


def _try_auto_copy(table_label: str, window_title_re: str) -> str:
    try:
        from pywinauto import Application, keyboard  # type: ignore[import-not-found]

        app = Application(backend="uia").connect(title_re=window_title_re, timeout=5)
        window = app.top_window()
        window.set_focus()
        keyboard.send_keys("^a")
        time.sleep(0.2)
        keyboard.send_keys("^c")
        time.sleep(0.4)
        return _read_clipboard_text()
    except Exception:
        pass
    return ""


def _is_interactive() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _capture_table(table_label: str, output_path: Path, window_title_re: str) -> None:
    auto = _try_auto_copy(table_label, window_title_re)
    if auto.strip():
        tsv = _normalize_clipboard_to_tsv(auto, output_path, table_label)
        if tsv is not None:
            output_path.write_text(tsv, encoding="utf-8")
            print(f"[auto] captured {table_label} -> {output_path}")
            return

    if not _is_interactive():
        raise RuntimeError(
            f"Cannot capture '{table_label}': pywinauto auto-copy failed and "
            f"stdin is not interactive (no manual fallback available). "
            f"Run from an interactive terminal or use dispatch_mastertune.py."
        )

    max_retries = 5
    for attempt in range(max_retries):
        print("")
        print(f"[manual] Export table: {table_label}")
        print("  1) In MasterTune, open the requested table.")
        print("  2) Click the table grid, press Ctrl+A then Ctrl+C.")
        input("  3) Press Enter here once copied...")
        text = _read_clipboard_text()

        if not text.strip():
            print(
                "  Clipboard appears empty. Ensure the table grid has focus, "
                "then press Ctrl+A, Ctrl+C."
            )
            if attempt < max_retries - 1:
                retry = input("  Retry this table? [Y/n]: ").strip().lower()
                if retry in {"", "y", "yes"}:
                    continue
            raise ValueError(f"User aborted capture for '{table_label}'")

        tsv = _normalize_clipboard_to_tsv(text, output_path, table_label)
        if tsv is not None:
            output_path.write_text(tsv, encoding="utf-8")
            matrix = parse_values_only_matrix(text, source_name="clipboard")
            if matrix:
                rows, cols = len(matrix), len(matrix[0])
                try:
                    parse_tsv_grid_text(text, source_name="clipboard")
                    print(f"[manual] captured {table_label} ({rows}x{cols}) -> {output_path}")
                except Exception:
                    print(
                        f"[manual] captured {table_label} ({rows}x{cols}, "
                        f"synthesized bins) -> {output_path}"
                    )
            else:
                print(f"[manual] captured {table_label} -> {output_path}")
            return

        debug_path = output_path.with_name(f"{output_path.stem}.clipboard_raw.txt")
        debug_path.write_text(text, encoding="utf-8")
        print(f"  Could not parse clipboard content. Raw saved to {debug_path}")
        if attempt < max_retries - 1:
            retry = input("  Retry this table? [Y/n]: ").strip().lower()
            if retry in {"", "y", "yes"}:
                continue
        raise ValueError(f"User aborted capture for '{table_label}'")

    raise ValueError(f"Max retries exceeded for '{table_label}'")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export MasterTune tables to TSV")
    parser.add_argument("--mt-file", required=True, help="Path to source .MT file")
    parser.add_argument("--out-dir", required=True, help="Output directory for TSV files")
    parser.add_argument("--ve-front", default="", help="Path override for VE front TSV")
    parser.add_argument("--ve-rear", default="", help="Path override for VE rear TSV")
    parser.add_argument("--lambda-tsv", default="", help="Path override for lambda TSV")
    parser.add_argument(
        "--app-path",
        default="",
        help="Deprecated: retained for compatibility; file association is used",
    )
    parser.add_argument(
        "--window-title-re",
        default=r"MasterTune.*",
        help="Window title regex for pywinauto focus/attach",
    )
    parser.add_argument(
        "--launch-wait-seconds",
        type=float,
        default=3.0,
        help="Wait time after launch before capture prompts begin",
    )
    parser.add_argument(
        "--axis-mode",
        choices=["map", "tps", "auto"],
        default="auto",
        help="Preferred VE table axis mode for prompts",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    mt_file = safe_path(args.mt_file, allow_parent_dir=True)
    out_dir = safe_path(args.out_dir, allow_parent_dir=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    ve_front = (
        safe_path(args.ve_front, allow_parent_dir=True)
        if args.ve_front
        else out_dir / "ve_front_map.tsv"
    )
    ve_rear = (
        safe_path(args.ve_rear, allow_parent_dir=True)
        if args.ve_rear
        else out_dir / "ve_rear_map.tsv"
    )
    lambda_tsv = (
        safe_path(args.lambda_tsv, allow_parent_dir=True)
        if args.lambda_tsv
        else out_dir / "lambda_map.tsv"
    )

    _launch_mt(mt_file)

    time.sleep(max(float(args.launch_wait_seconds), 0.0))

    if args.axis_mode == "auto":
        print("")
        print("[axis] Select table axis mode for this tune:")
        print("  1) MAP (kPa)")
        print("  2) TPS (Percent)")
        axis_choice = input("Choose [1/2] (default 1): ").strip()
        axis_mode = "tps" if axis_choice == "2" else "map"
    else:
        axis_mode = args.axis_mode

    if axis_mode == "tps":
        captures: Dict[str, Path] = {
            "Main Lambda": lambda_tsv,
            "VE TPS Front Cyl (Percent)": ve_front,
            "VE TPS Rear Cyl (Percent)": ve_rear,
        }
    else:
        captures = {
            "Main Lambda": lambda_tsv,
            "VE MAP Front Cyl (kPa)": ve_front,
            "VE MAP Rear Cyl (kPa)": ve_rear,
        }
    for label, target in captures.items():
        _capture_table(label, target, args.window_title_re)

    print("")
    print("MasterTune table export complete")
    print(f"- mt_file: {mt_file}")
    print(f"- out_dir: {out_dir}")
    print(f"- ve_front: {ve_front}")
    print(f"- ve_rear: {ve_rear}")
    print(f"- lambda_tsv: {lambda_tsv}")


if __name__ == "__main__":
    main()
