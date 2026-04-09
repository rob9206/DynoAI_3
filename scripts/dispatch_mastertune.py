"""
Fully automated MasterTune ingest dispatcher.

Maintains a persistent queue JSON so runs can be interrupted and resumed.
Uses an unattended UI worker (pywinauto) to open files, navigate tables,
copy grids, and ingest — no manual input required.

Usage::

    python scripts/dispatch_mastertune.py
        --calibration-dir "C:/Users/.../Calibrations"
        --library-dir "c:/Dev/DynoAI_3/data/calibration_library"
        --axis-mode map

Resume after interruption (picks up where it left off)::

    python scripts/dispatch_mastertune.py --resume
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
INGEST_TSV = SCRIPTS_DIR / "ingest_mastertune_tsv.py"
GENERATE_TEMPLATES = SCRIPTS_DIR / "generate_mastertune_tsv_templates.py"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dynoai.core.io_contracts import safe_path  # noqa: E402

VALID_EXTENSIONS = {".mt7", ".mt8", ".mt9"}
DEFAULT_QUEUE_PATH = ROOT_DIR / "data" / "mastertune_catalog" / "dispatch_queue.json"
DEFAULT_CAL_DIR = Path(r"C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations")
DEBUG_LOG_PATH = ROOT_DIR / "debug-f2c3c9.log"
DEBUG_SESSION_ID = "f2c3c9"
DEBUG_RUN_ID = f"run_{int(time.time() * 1000)}"
PANIC_ESC_WINDOW_S = 1.0
PANIC_ESC_VK = 0x1B
# After WM_CLOSE, wait briefly so the process can exit before the next os.startfile.
MT_CLOSE_GRACE_S = 1.5
_PANIC_LAST_ESC_TS = 0.0
_PANIC_ESC_WAS_DOWN = False

STATUS_PENDING = "pending"
STATUS_EXPORTING = "exporting"
STATUS_EXPORTED = "exported"
STATUS_INGESTED = "ingested"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


def _dbg(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    try:
        payload = {
            "sessionId": DEBUG_SESSION_ID,
            "runId": DEBUG_RUN_ID,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _panic_poll_or_raise(context: str) -> None:
    """Stop immediately when ESC is pressed twice quickly."""
    global _PANIC_LAST_ESC_TS, _PANIC_ESC_WAS_DOWN

    if sys.platform != "win32":
        return
    try:
        import ctypes

        now = time.monotonic()
        is_down = bool(ctypes.windll.user32.GetAsyncKeyState(PANIC_ESC_VK) & 0x8000)

        if is_down and not _PANIC_ESC_WAS_DOWN:
            delta = now - _PANIC_LAST_ESC_TS if _PANIC_LAST_ESC_TS > 0 else None
            if delta is not None and delta <= PANIC_ESC_WINDOW_S:
                # region agent log
                _dbg(
                    "H7",
                    "dispatch_mastertune.py:_panic_poll_or_raise",
                    "panic_double_esc_trigger",
                    {"context": context, "delta_s": round(delta, 4)},
                )
                # endregion
                print("PANIC STOP: double ESC detected. Saving queue and exiting...")
                raise KeyboardInterrupt("panic_double_esc")

            _PANIC_LAST_ESC_TS = now
            # region agent log
            _dbg(
                "H7",
                "dispatch_mastertune.py:_panic_poll_or_raise",
                "panic_esc_press",
                {"context": context},
            )
            # endregion

        _PANIC_ESC_WAS_DOWN = is_down
    except KeyboardInterrupt:
        raise
    except Exception:
        return


def _sleep_with_panic(seconds: float, context: str) -> None:
    end = time.monotonic() + max(0.0, seconds)
    while True:
        _panic_poll_or_raise(context)
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.05, remaining))


def _scan_mt_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in VALID_EXTENSIONS:
            files.append(path)
    return files


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


def _looks_filled(tsv_path: Path) -> bool:
    if not tsv_path.exists():
        return False
    lines = [ln for ln in tsv_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    tokens = set()
    for line in lines[1:]:
        for part in line.split("\t")[1:]:
            v = part.strip()
            if v:
                tokens.add(v)
    return len(tokens) > 6


def _should_ignore_window_title(title: str) -> bool:
    """Exclude shell/terminal windows that may echo the regex in their title."""
    title_lower = (title or "").strip().lower()
    if not title_lower:
        return False
    return any(
        marker in title_lower
        for marker in (
            "command prompt",
            "powershell",
            "windows powershell",
            "terminal",
        )
    )


# ── Queue persistence ─────────────────────────────────────────────────

def _load_queue(path: Path) -> Dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"created_at": "", "config": {}, "items": []}


def _save_queue(path: Path, queue: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=2, default=str), encoding="utf-8")


def _build_queue(
    cal_dir: Path,
    library_dir: Optional[Path],
    axis_mode: str,
    max_files: int,
    file_contains: List[str],
) -> Dict[str, Any]:
    files = _scan_mt_files(cal_dir)
    if file_contains:
        normalized = [p.lower() for p in file_contains if p.strip()]
        files = [f for f in files if any(p in f.name.lower() for p in normalized)]
    if max_files > 0:
        files = files[:max_files]

    items: List[Dict[str, Any]] = []
    for f in files:
        items.append({
            "mt_file": str(f),
            "status": STATUS_PENDING,
            "reason": "",
            "message": "",
            "retries": 0,
            "updated_at": "",
        })
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "calibration_dir": str(cal_dir),
            "library_dir": str(library_dir) if library_dir else "",
            "axis_mode": axis_mode,
        },
        "items": items,
    }


# ── Unattended UI worker ──────────────────────────────────────────────

def _ensure_templates(mt_file: Path) -> None:
    tsv = _tsv_paths(mt_file)
    if all(tsv[k].exists() for k in ("ve_front", "ve_rear", "lambda")):
        return
    cmd = [
        "python", str(GENERATE_TEMPLATES),
        "--mt-file", str(mt_file),
        "--output-dir", str(_template_dir(mt_file)),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _get_mt_app(title_re: str, timeout: float = 15.0) -> Any:
    """Connect to MasterTune using win32 backend and return (app, window)."""
    import re
    from pywinauto import Application, Desktop  # noqa: E402

    deadline = time.time() + timeout
    while time.time() < deadline:
        # Primary strategy: attach via Application.connect.
        try:
            app = Application(backend="win32").connect(title_re=title_re, timeout=2)
            return app, app.top_window()
        except Exception:
            pass

        # Fallback: enumerate desktop windows and attach by handle/title.
        try:
            pattern = re.compile(title_re)
            for candidate in Desktop(backend="win32").windows():
                try:
                    if not candidate.is_visible():
                        continue
                    title = candidate.window_text() or ""
                    if not title:
                        continue
                    if _should_ignore_window_title(title):
                        continue
                    # Strict regex match only.
                    if pattern.search(title):
                        app = Application(backend="win32").connect(handle=candidate.handle, timeout=1)
                        return app, candidate
                except Exception:
                    continue
        except Exception:
            pass

        _sleep_with_panic(1.0, "_get_mt_app:retry_wait")
    return None, None


def _force_accept_tab_enter(window_title_re: str, attempts: int = 3) -> None:
    """Immediately try Tab+Enter on MasterTune startup dialog."""
    from pywinauto import Desktop, keyboard as kbd  # noqa: E402

    for _ in range(attempts):
        dialog = None
        for candidate in Desktop(backend="win32").windows(title_re=window_title_re):
            try:
                if not candidate.is_visible():
                    continue
                accept_btn = candidate.child_window(title_re=".*I Accept.*")
                if accept_btn.exists(timeout=0.2):
                    dialog = candidate
                    break
            except Exception:
                continue
        if dialog is None:
            # Do not send Tab/Enter blindly to main UI.
            return
        try:
            dialog.set_focus()
        except Exception:
            _sleep_with_panic(0.3, "_force_accept_tab_enter:focus_retry")
            continue
        try:
            _sleep_with_panic(0.2, "_force_accept_tab_enter:pre_tab")
            kbd.send_keys("{TAB}")
            _sleep_with_panic(0.15, "_force_accept_tab_enter:pre_enter")
            kbd.send_keys("{ENTER}")
            _sleep_with_panic(0.5, "_force_accept_tab_enter:post_enter")
        except Exception:
            pass


def _clear_clipboard() -> None:
    """Empty the clipboard so stale data doesn't pollute the next capture."""
    import subprocess as sp
    try:
        sp.run(
            ["powershell", "-NoProfile", "-Command",
             "Set-Clipboard -Value $null"],
            check=False, capture_output=True, text=True,
        )
    except Exception:
        pass


def _read_clipboard() -> str:
    import subprocess as sp

    try:
        probe = sp.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            check=False, capture_output=True, text=True,
        )
        text = probe.stdout or ""
        if text.strip():
            return text
    except Exception:
        pass

    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        try:
            text = root.clipboard_get()
        except tkinter.TclError:
            text = ""
        finally:
            root.destroy()
        return text
    except Exception:
        return ""


def _navigate_table(table_name: str, window_title_re: str) -> bool:
    """Navigate to a table in MasterTune via the Table Selection menu.

    MasterTune menu bar: File  Edit  Setup  Table Selection  Table Comparison  Tools  Help
    We use keyboard: Alt to activate menu bar, then Right arrow to
    "Table Selection" (4th item), Enter to open it, then type the
    table name to jump in the list.
    """
    _, window = _get_mt_app(window_title_re, timeout=5)
    if window is None:
        print(f"      nav: window not found")
        return False

    try:
        window.set_focus()
        _sleep_with_panic(0.5, "_navigate_table:post_focus")

        # Try menu_select first (works if menus are standard)
        try:
            window.menu_select("Table Selection->" + table_name)
            _sleep_with_panic(0.7, "_navigate_table:post_menu_select")
            # region agent log
            _dbg(
                "H3",
                "dispatch_mastertune.py:_navigate_table",
                "nav_menu_select_ok",
                {
                    "table_name": table_name,
                    "title_re": window_title_re,
                },
            )
            # endregion
            print(f"      nav: menu_select OK")
            return True
        except Exception:
            # region agent log
            _dbg(
                "H3",
                "dispatch_mastertune.py:_navigate_table",
                "nav_menu_select_failed",
                {"table_name": table_name, "title_re": window_title_re},
            )
            # endregion
            print("      nav: menu_select failed")
            return False
    except Exception as exc:
        # region agent log
        _dbg(
            "H3",
            "dispatch_mastertune.py:_navigate_table",
            "nav_exception",
            {"table_name": table_name, "title_re": window_title_re, "error": f"{type(exc).__name__}: {exc}"},
        )
        # endregion
        print(f"      nav: failed ({exc})")
        return False


def _is_mastertune_foreground(window_title_re: str, expected_handle: int) -> bool:
    """Return True when foreground HWND matches selected MasterTune window."""
    import re
    import win32gui  # type: ignore[import-not-found]

    try:
        active_handle = int(win32gui.GetForegroundWindow() or 0)
        active_title = (win32gui.GetWindowText(active_handle) or "").strip()

        same_handle = active_handle == int(expected_handle or 0)
        regex_match = bool(re.search(window_title_re, active_title)) if active_title else False
        contains_mt = "mastertune" in active_title.lower() if active_title else False
        return same_handle or regex_match or contains_mt
    except Exception:
        return False


def _auto_capture_grid(window_title_re: str) -> str:
    """Focus MasterTune, click table corner selector, Ctrl+C, return clipboard."""
    from pywinauto import keyboard as kbd, mouse  # noqa: E402

    _, window = _get_mt_app(window_title_re, timeout=10)
    if window is None:
        return ""
    try:
        _panic_poll_or_raise("_auto_capture_grid:start")
        window.set_focus()
        _sleep_with_panic(0.6, "_auto_capture_grid:post_focus")

        window_handle = int(getattr(window, "handle", 0) or 0)
        if not _is_mastertune_foreground(window_title_re, window_handle):
            # region agent log
            _dbg(
                "H4",
                "dispatch_mastertune.py:_auto_capture_grid",
                "foreground_blocked",
                {"title_re": window_title_re, "window_handle": window_handle},
            )
            # endregion
            print("      capture: MasterTune not foreground, skipping key send")
            return ""

        # Click the top-left table selector corner (intersection near RPM/header),
        # which highlights the entire grid in MasterTune.
        rect = window.rectangle()
        click_x = rect.left + int((rect.right - rect.left) * 0.02)
        click_y = rect.top + int((rect.bottom - rect.top) * 0.185)
        mouse.click(coords=(click_x, click_y))
        _sleep_with_panic(0.25, "_auto_capture_grid:post_click")

        _clear_clipboard()
        kbd.send_keys("^c")
        _sleep_with_panic(0.5, "_auto_capture_grid:post_copy")
    except Exception as exc:
        print(f"      capture: failed ({exc})")
        return ""
    text = _read_clipboard()
    return text


def _normalize_clipboard_to_tsv(text: str, template_path: Path) -> Optional[str]:
    from api.services.external_scrapers.mastertune_parser import (
        parse_tsv_grid_text,
        parse_tsv_grid_file,
        parse_values_only_matrix,
    )

    text_l = text.lower()
    preview_lines = [ln.strip()[:160] for ln in text.splitlines()[:4]]
    # region agent log
    _dbg(
        "H10",
        "dispatch_mastertune.py:_normalize_clipboard_to_tsv",
        "clipboard_preview",
        {
            "template_path": str(template_path),
            "preview_lines": preview_lines,
            "line_count": len(text.splitlines()),
            "char_count": len(text),
        },
    )
    # endregion
    if (
        "cranking fuel" in text_l
        or "engine deg" in text_l
        or "\tcrank\t" in text_l
    ):
        # region agent log
        _dbg(
            "H8",
            "dispatch_mastertune.py:_normalize_clipboard_to_tsv",
            "reject_non_ve_clipboard",
            {"template_path": str(template_path)},
        )
        # endregion
        return None

    try:
        parse_tsv_grid_text(text, source_name="clipboard")
        return text
    except Exception:
        pass

    template = parse_tsv_grid_file(template_path)
    matrix = parse_values_only_matrix(text, source_name="clipboard")
    if matrix is None:
        return None

    actual_rows = len(matrix)
    actual_cols = len(matrix[0]) if matrix else 0
    target_rows = len(template.row_bins)
    target_cols = len(template.col_bins)
    # region agent log
    _dbg(
        "H8",
        "dispatch_mastertune.py:_normalize_clipboard_to_tsv",
        "clipboard_matrix_dims",
        {
            "template_path": str(template_path),
            "actual_rows": actual_rows,
            "actual_cols": actual_cols,
            "target_rows": target_rows,
            "target_cols": target_cols,
        },
    )
    # endregion

    # Very narrow captures (e.g. single column values like cranking mS) are not
    # valid VE/lambda maps and should always be rejected.
    if actual_cols <= 2:
        # region agent log
        _dbg(
            "H8",
            "dispatch_mastertune.py:_normalize_clipboard_to_tsv",
            "reject_too_narrow_matrix",
            {
                "template_path": str(template_path),
                "actual_rows": actual_rows,
                "actual_cols": actual_cols,
            },
        )
        # endregion
        return None

    if actual_rows == target_rows and actual_cols == target_cols:
        return _build_tsv(template.row_bins, template.col_bins, matrix)
    if actual_rows == target_rows and actual_cols == target_cols + 1:
        return _build_tsv(template.row_bins, template.col_bins, [r[1:] for r in matrix])
    if actual_rows == target_rows + 1 and actual_cols == target_cols:
        return _build_tsv(template.row_bins, template.col_bins, matrix[1:])
    if actual_rows == target_rows + 1 and actual_cols == target_cols + 1:
        return _build_tsv(template.row_bins, template.col_bins, [r[1:] for r in matrix[1:]])

    # Accept larger matrix captures by rebuilding a TSV with synthetic bins.
    # This handles tunes whose table dimensions differ from template defaults.
    if actual_rows >= 8 and actual_cols >= 8:
        row_bins = _linspace(template.row_bins[0], template.row_bins[-1], actual_rows)
        col_bins = _linspace(template.col_bins[0], template.col_bins[-1], actual_cols)
        # region agent log
        _dbg(
            "H8",
            "dispatch_mastertune.py:_normalize_clipboard_to_tsv",
            "accept_dim_mismatch_resample",
            {
                "template_path": str(template_path),
                "actual_rows": actual_rows,
                "actual_cols": actual_cols,
                "target_rows": target_rows,
                "target_cols": target_cols,
            },
        )
        # endregion
        return _build_tsv(row_bins, col_bins, matrix)

    # Reject other mismatches.
    # region agent log
    _dbg(
        "H8",
        "dispatch_mastertune.py:_normalize_clipboard_to_tsv",
        "reject_dim_mismatch",
        {
            "template_path": str(template_path),
            "actual_rows": actual_rows,
            "actual_cols": actual_cols,
            "target_rows": target_rows,
            "target_cols": target_cols,
        },
    )
    # endregion
    return None


def _linspace(start: float, end: float, count: int) -> List[float]:
    if count <= 1:
        return [float(start)]
    step = (float(end) - float(start)) / float(count - 1)
    return [round(float(start) + step * float(i), 2) for i in range(count)]


def _build_tsv(
    row_bins: List[float], col_bins: List[float], matrix: List[List[float]]
) -> str:
    header = ["RPM"] + [str(v) for v in col_bins]
    out = ["\t".join(header)]
    for rpm, row in zip(row_bins, matrix):
        out.append("\t".join([str(rpm)] + [str(v) for v in row]))
    return "\n".join(out) + "\n"


def _dismiss_accept_dialog(window_title_re: str, timeout: float = 12.0) -> bool:
    """Dismiss the MasterTune CAUTION/disclaimer dialog via keyboard.

    The dialog has two buttons: "I Decline" (focused by default) and
    "I Accept" below it.  We Tab to "I Accept" and press Enter.
    Falls back to trying pywinauto button click if keyboard doesn't work.
    """
    from pywinauto import Desktop, keyboard as kbd  # noqa: E402

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            dlg = None
            for candidate in Desktop(backend="win32").windows(title_re=window_title_re):
                try:
                    if not candidate.is_visible():
                        continue
                    accept_btn = candidate.child_window(title_re=".*I Accept.*")
                    if accept_btn.exists(timeout=0.2):
                        dlg = candidate
                        break
                except Exception:
                    continue
            if dlg is None:
                _sleep_with_panic(0.5, "_dismiss_accept_dialog:wait_for_dialog")
                continue
            dlg.set_focus()
            _sleep_with_panic(0.5, "_dismiss_accept_dialog:post_focus")

            # Prefer direct click on the explicit button; fallback to Tab+Enter.
            clicked = False
            try:
                btn = dlg.child_window(title_re=".*I Accept.*")
                if btn.exists(timeout=0.3) and btn.is_visible():
                    btn.click_input()
                    clicked = True
            except Exception:
                pass
            if not clicked:
                kbd.send_keys("{TAB}")
                _sleep_with_panic(0.3, "_dismiss_accept_dialog:tab_to_accept")
                kbd.send_keys("{ENTER}")
            _sleep_with_panic(1.5, "_dismiss_accept_dialog:post_accept")

            # Verify we no longer see a visible accept dialog.
            try:
                still_visible = False
                for candidate in Desktop(backend="win32").windows(title_re=window_title_re):
                    try:
                        if not candidate.is_visible():
                            continue
                        accept_btn = candidate.child_window(title_re=".*I Accept.*")
                        if accept_btn.exists(timeout=0.2):
                            still_visible = True
                            break
                    except Exception:
                        continue
                if not still_visible:
                    print("    dismissed startup dialog")
                    return True
            except Exception:
                print("    dismissed startup dialog")
                return True

            # Dialog is still present; retry until timeout.
        except Exception:
            _sleep_with_panic(1.0, "_dismiss_accept_dialog:retry_after_error")
            continue

    print("    no accept dialog detected")
    return False


def _dismiss_warning_dialog(window_title_re: str, timeout: float = 1.0) -> bool:
    """Dismiss MasterTune warning modals with an OK button.

    Some tunes open a blocking warning popup (e.g. discontinued/high compression
    warning). This function searches visible windows from the same process and
    clicks OK when detected.
    """
    from pywinauto import Desktop, keyboard as kbd  # noqa: E402

    deadline = time.time() + max(0.2, timeout)
    dismissed_any = False
    seen_any_mt = False
    ok_candidates = 0
    warning_candidates = 0
    dismissed_count = 0

    while time.time() < deadline:
        try:
            # Collect process IDs belonging to visible MasterTune windows.
            mt_pids = set()
            for mt_win in Desktop(backend="win32").windows(title_re=window_title_re):
                try:
                    if mt_win.is_visible():
                        mt_pids.add(int(mt_win.process_id()))
                        seen_any_mt = True
                except Exception:
                    continue

            if not mt_pids:
                _sleep_with_panic(0.1, "_dismiss_warning_dialog:wait_for_mt_pid")
                continue

            # Fast path: if current foreground window is a MasterTune warning modal,
            # press Enter directly on that modal.
            try:
                import win32gui  # type: ignore[import-not-found]
                import win32process  # type: ignore[import-not-found]

                fg_hwnd = int(win32gui.GetForegroundWindow() or 0)
                fg_title = (win32gui.GetWindowText(fg_hwnd) or "").strip()
                _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
                fg_title_l = fg_title.lower()

                # region agent log
                _dbg(
                    "H1",
                    "dispatch_mastertune.py:_dismiss_warning_dialog",
                    "warning_foreground_probe",
                    {
                        "title_re": window_title_re,
                        "fg_hwnd": fg_hwnd,
                        "fg_pid": int(fg_pid or 0),
                        "fg_title": fg_title,
                        "pid_match_mt": int(fg_pid or 0) in mt_pids,
                    },
                )
                # endregion

                if int(fg_pid or 0) in mt_pids and "warning" in fg_title_l:
                    kbd.send_keys("{ENTER}")
                    dismissed_any = True
                    dismissed_count += 1
                    # region agent log
                    _dbg(
                        "H1",
                        "dispatch_mastertune.py:_dismiss_warning_dialog",
                        "warning_foreground_enter",
                        {"fg_title": fg_title, "fg_pid": int(fg_pid or 0)},
                    )
                    # endregion
                    print("    dismissed warning dialog")
                    _sleep_with_panic(0.2, "_dismiss_warning_dialog:post_foreground_enter")
                    continue
            except Exception:
                pass

            found_warning = False
            for candidate in Desktop(backend="win32").windows():
                try:
                    if not candidate.is_visible():
                        continue
                    if int(candidate.process_id()) not in mt_pids:
                        continue

                    win_text = (candidate.window_text() or "").lower()
                    ok_btn = candidate.child_window(title_re=r"(?i).*ok.*")
                    has_ok = ok_btn.exists(timeout=0.1)
                    if not has_ok:
                        # Fallback: look for any visible child control with "ok" text.
                        for ctrl in candidate.children():
                            try:
                                t = (ctrl.window_text() or "").strip().lower()
                            except Exception:
                                continue
                            if "ok" in t:
                                has_ok = True
                                break
                    if not has_ok:
                        continue
                    ok_candidates += 1

                    # Match warning by title/body text when possible.
                    warning_text_present = (
                        "warning" in win_text
                        or "high compression" in win_text
                        or "discontinued" in win_text
                    )
                    if not warning_text_present:
                        try:
                            # Broader fallback: inspect aggregated window text.
                            blob = " ".join(
                                (t or "").strip().lower() for t in (candidate.texts() or [])
                            )
                            if (
                                "warning" in blob
                                or "high compression" in blob
                                or "discontinued" in blob
                            ):
                                warning_text_present = True
                        except Exception:
                            pass
                    if not warning_text_present:
                        for ctrl in candidate.children():
                            try:
                                t = (ctrl.window_text() or "").lower()
                            except Exception:
                                continue
                            if "warning" in t or "high compression" in t or "discontinued" in t:
                                warning_text_present = True
                                break

                    if not warning_text_present:
                        continue

                    found_warning = True
                    warning_candidates += 1
                    candidate.set_focus()
                    _sleep_with_panic(0.1, "_dismiss_warning_dialog:post_focus")
                    clicked = False
                    try:
                        if ok_btn.is_visible():
                            ok_btn.click_input()
                            clicked = True
                    except Exception:
                        pass
                    if not clicked:
                        kbd.send_keys("{ENTER}")
                    dismissed_count += 1
                    # region agent log
                    _dbg(
                        "H1",
                        "dispatch_mastertune.py:_dismiss_warning_dialog",
                        "warning_dismiss_attempt",
                        {
                            "title_re": window_title_re,
                            "window_title": candidate.window_text() or "",
                            "pid": int(candidate.process_id()),
                            "dismiss_method": "click_ok" if clicked else "enter_key",
                        },
                    )
                    # endregion
                    print("    dismissed warning dialog")
                    dismissed_any = True
                    _sleep_with_panic(0.2, "_dismiss_warning_dialog:post_dismiss")
                except Exception:
                    continue

            if not found_warning:
                # region agent log
                _dbg(
                    "H2",
                    "dispatch_mastertune.py:_dismiss_warning_dialog",
                    "warning_scan_summary",
                    {
                        "title_re": window_title_re,
                        "timeout": timeout,
                        "seen_any_mt": seen_any_mt,
                        "ok_candidates": ok_candidates,
                        "warning_candidates": warning_candidates,
                        "dismissed_count": dismissed_count,
                        "dismissed_any": dismissed_any,
                        "exit_reason": "no_warning_found",
                    },
                )
                # endregion
                return dismissed_any
        except Exception:
            pass
        _sleep_with_panic(0.1, "_dismiss_warning_dialog:scan_loop_wait")

    # region agent log
    _dbg(
        "H2",
        "dispatch_mastertune.py:_dismiss_warning_dialog",
        "warning_scan_summary",
        {
            "title_re": window_title_re,
            "timeout": timeout,
            "seen_any_mt": seen_any_mt,
            "ok_candidates": ok_candidates,
            "warning_candidates": warning_candidates,
            "dismissed_count": dismissed_count,
            "dismissed_any": dismissed_any,
            "exit_reason": "timeout",
        },
    )
    # endregion
    return dismissed_any


def _dismiss_connection_wizard(window_title_re: str, timeout: float = 0.4) -> bool:
    """Dismiss MasterTune connection wizard modal if it appears."""
    from pywinauto import Desktop, keyboard as kbd  # noqa: E402

    deadline = time.time() + max(0.1, timeout)
    dismissed = False
    while time.time() < deadline:
        try:
            mt_pids = set()
            for mt_win in Desktop(backend="win32").windows(title_re=window_title_re):
                try:
                    if mt_win.is_visible():
                        mt_pids.add(int(mt_win.process_id()))
                except Exception:
                    continue
            if not mt_pids:
                return dismissed

            found = False
            for candidate in Desktop(backend="win32").windows():
                try:
                    if not candidate.is_visible():
                        continue
                    if int(candidate.process_id()) not in mt_pids:
                        continue
                    parts = [candidate.window_text() or ""]
                    try:
                        parts.extend(candidate.texts() or [])
                    except Exception:
                        pass
                    blob = " ".join(parts).lower()
                    is_wizard = (
                        "connection wizard" in blob
                        or "manual interface selection" in blob
                        or "save, restore, open and configure calibration" in blob
                    )
                    if not is_wizard:
                        continue
                    found = True
                    candidate.set_focus()
                    clicked = False
                    try:
                        cancel_btn = candidate.child_window(title_re=r"(?i).*cancel.*")
                        if cancel_btn.exists(timeout=0.1):
                            cancel_btn.click_input()
                            clicked = True
                    except Exception:
                        pass
                    if not clicked:
                        kbd.send_keys("{ESC}")
                    dismissed = True
                    # region agent log
                    _dbg(
                        "H9",
                        "dispatch_mastertune.py:_dismiss_connection_wizard",
                        "wizard_dismiss_attempt",
                        {
                            "window_title": candidate.window_text() or "",
                            "dismiss_method": "cancel_click" if clicked else "esc_key",
                        },
                    )
                    # endregion
                    print("    dismissed connection wizard")
                    _sleep_with_panic(0.15, "_dismiss_connection_wizard:post_dismiss")
                except Exception:
                    continue
            if not found:
                return dismissed
        except Exception:
            return dismissed
    return dismissed


def _export_one_file(
    mt_file: Path, axis_mode: str, window_title_re: str, max_table_retries: int = 3
) -> Optional[str]:
    """
    Unattended export of all 3 tables for one MT file.

    Returns None on success, or an error message string on failure.
    """
    import os

    if os.name != "nt":
        return "unattended export only supported on Windows"

    _ensure_templates(mt_file)
    tsv = _tsv_paths(mt_file)

    if all(_looks_filled(tsv[k]) for k in ("ve_front", "ve_rear", "lambda")):
        return None

    # region agent log
    _dbg(
        "H5",
        "dispatch_mastertune.py:_export_one_file",
        "export_start",
        {"mt_file": str(mt_file), "axis_mode": axis_mode},
    )
    # endregion

    os.startfile(str(mt_file))
    _sleep_with_panic(0.6, "_export_one_file:post_startfile")

    # Wait for MasterTune to fully load (title shows "Advanced Mode Active").
    # Some files load slowly and/or show a startup accept dialog.
    # We try targeted dismissal first; if still stuck, fall back to blind
    # Tab+Enter on the foreground window belonging to the MasterTune process.
    import win32gui  # type: ignore[import-not-found]
    import win32process  # type: ignore[import-not-found]
    from pywinauto import Desktop, keyboard as kbd_mod  # noqa: E402

    def _mt_pids() -> set:
        pids: set = set()
        try:
            for w in Desktop(backend="win32").windows(title_re=window_title_re):
                try:
                    if w.is_visible():
                        pids.add(int(w.process_id()))
                except Exception:
                    pass
        except Exception:
            pass
        return pids

    ready_deadline = time.time() + 15.0
    stuck_since = time.time()
    while time.time() < ready_deadline:
        _panic_poll_or_raise("_export_one_file:wait_for_ready")
        _force_accept_tab_enter(window_title_re, attempts=1)
        _dismiss_accept_dialog(window_title_re, timeout=0.4)
        _dismiss_warning_dialog(window_title_re, timeout=0.3)
        _dismiss_connection_wizard(window_title_re, timeout=0.2)
        try:
            fg_hwnd = int(win32gui.GetForegroundWindow() or 0)
            fg_title = (win32gui.GetWindowText(fg_hwnd) or "").strip()
            fg_title_l = fg_title.lower()
            if "advanced mode active" in fg_title_l:
                _dbg("H5", "dispatch_mastertune.py:_export_one_file", "ready_advanced_mode",
                     {"fg_title": fg_title, "elapsed_ms": int((time.time() - stuck_since) * 1000)})
                break
            # If foreground belongs to MasterTune process and we've been
            # waiting > 1.5 s, send Tab+Enter blind to dismiss any modal.
            if time.time() - stuck_since > 1.5:
                try:
                    _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
                    if int(fg_pid or 0) in _mt_pids():
                        kbd_mod.send_keys("{TAB}")
                        _sleep_with_panic(0.15, "_export_one_file:blind_tab")
                        kbd_mod.send_keys("{ENTER}")
                        _dbg("H5", "dispatch_mastertune.py:_export_one_file", "blind_tab_enter",
                             {"fg_title": fg_title, "fg_pid": int(fg_pid or 0)})
                except Exception:
                    pass
        except Exception:
            pass
        _sleep_with_panic(0.3, "_export_one_file:wait_for_ready_sleep")

    _sleep_with_panic(0.3, "_export_one_file:post_dialogs")

    # Some tunes name lambda as "Main Air Fuel Ratio" instead of "Main Lambda".
    if axis_mode == "tps":
        table_candidates = [
            (["Main Lambda", "Main Air-Fuel Ratio", "Main Air Fuel Ratio"], tsv["lambda"]),
            (["VE Front Cyl", "VE TPS Front Cyl (Percent)", "VE TPS Front"], tsv["ve_front"]),
            (["VE Rear Cyl", "VE TPS Rear Cyl (Percent)", "VE TPS Rear"], tsv["ve_rear"]),
        ]
    else:
        table_candidates = [
            (["Main Lambda", "Main Air-Fuel Ratio", "Main Air Fuel Ratio"], tsv["lambda"]),
            (["VE Front Cyl", "VE MAP Front Cyl (kPa)", "VE MAP Front"], tsv["ve_front"]),
            (["VE Rear Cyl", "VE MAP Rear Cyl (kPa)", "VE MAP Rear"], tsv["ve_rear"]),
        ]

    for candidate_names, tsv_path in table_candidates:
        display_name = candidate_names[0]
        if _looks_filled(tsv_path):
            print(f"    {display_name}: already filled")
            continue

        captured = False
        for attempt in range(max_table_retries):
            _panic_poll_or_raise(f"_export_one_file:table_attempt:{display_name}:{attempt+1}")
            print(f"    {display_name}: attempt {attempt + 1}")
            _dismiss_warning_dialog(window_title_re, timeout=0.2)
            _dismiss_connection_wizard(window_title_re, timeout=0.2)
            for nav_name in candidate_names:
                _panic_poll_or_raise(f"_export_one_file:nav:{nav_name}")
                _dismiss_warning_dialog(window_title_re, timeout=0.15)
                _dismiss_connection_wizard(window_title_re, timeout=0.15)
                nav_ok = _navigate_table(nav_name, window_title_re)
                if not nav_ok:
                    # Don't capture from whatever table is currently selected;
                    # move to next alias candidate instead.
                    continue
                _sleep_with_panic(0.55, f"_export_one_file:post_navigate:{nav_name}")

                clipboard = _auto_capture_grid(window_title_re)
                if not clipboard.strip():
                    _dismiss_warning_dialog(window_title_re, timeout=0.15)
                    continue

                result = _normalize_clipboard_to_tsv(clipboard, tsv_path)
                if result is not None:
                    tsv_path.write_text(result, encoding="utf-8")
                    captured = True
                    break
            if captured:
                break
            print(f"    {display_name}: clipboard empty or unparseable")
            _sleep_with_panic(0.5, f"_export_one_file:retry_wait:{display_name}")

        if not captured:
            # region agent log
            _dbg(
                "H3",
                "dispatch_mastertune.py:_export_one_file",
                "table_capture_failed",
                {"mt_file": str(mt_file), "table": display_name, "retries": max_table_retries},
            )
            # endregion
            return f"failed to capture '{display_name}' after {max_table_retries} attempts"

    return None


def _ingest_one(
    mt_file: Path,
    library_dir: Optional[Path],
    queue_path: Path,
    item_index: int,
    item_status: str,
    item_retries: int,
) -> Optional[str]:
    tsv = _tsv_paths(mt_file)
    cmd = [
        "python", str(INGEST_TSV),
        "--mt-file", str(mt_file),
        "--ve-front-tsv", str(tsv["ve_front"]),
        "--ve-rear-tsv", str(tsv["ve_rear"]),
        "--lambda-tsv", str(tsv["lambda"]),
        "--notes", f"dispatch-ingest {mt_file.name}",
        "--operator", "dispatch",
        "--queue-path", str(queue_path),
        "--queue-item-index", str(item_index),
        "--queue-status", item_status,
        "--queue-retries", str(item_retries),
        "--quality-status", "pending_audit",
    ]
    if library_dir:
        cmd.extend(["--library-dir", str(library_dir)])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return None
    return result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"


def _close_mastertune_windows(window_title_re: str, grace_s: float = MT_CLOSE_GRACE_S) -> int:
    """Post WM_CLOSE to each visible top-level window whose title matches ``window_title_re``.

    Prevents MasterTune instances from piling up when the dispatcher opens many files.
    Returns how many windows were sent WM_CLOSE (0 if none matched or platform unsupported).
    """
    if sys.platform != "win32":
        return 0
    try:
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]
    except ImportError:
        return 0
    try:
        pattern = re.compile(window_title_re)
    except re.error:
        return 0
    hwnds: List[int] = []

    def _enum(hwnd: int, _: Any) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        if not title:
            return
        if _should_ignore_window_title(title):
            return
        if pattern.search(title):
            hwnds.append(int(hwnd))

    try:
        win32gui.EnumWindows(_enum, None)
    except Exception:
        return 0
    for hwnd in hwnds:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass
    if hwnds and grace_s > 0:
        time.sleep(grace_s)
    return len(hwnds)


# ── Dispatch loop ─────────────────────────────────────────────────────

def _run_dispatch(
    queue: Dict[str, Any],
    queue_path: Path,
    window_title_re: str,
    max_retries: int,
    inter_file_delay: float,
    close_after_file: bool = True,
) -> None:
    config = queue["config"]
    library_dir = Path(config["library_dir"]) if config.get("library_dir") else None
    axis_mode = config.get("axis_mode", "map")
    items = queue["items"]

    actionable = [
        (idx, item) for idx, item in enumerate(items)
        if item["status"] in (STATUS_PENDING, STATUS_EXPORTING, STATUS_EXPORTED)
        and item["retries"] < max_retries
    ]

    total = len(items)
    print(f"Dispatch: {len(actionable)} actionable / {total} total items")

    for seq, (idx, item) in enumerate(actionable, 1):
        _panic_poll_or_raise("_run_dispatch:loop_start")
        mt_file = Path(item["mt_file"])
        now = datetime.now(timezone.utc).isoformat()
        print(f"\n[{seq}/{len(actionable)}] {mt_file.name}  (attempt {item['retries'] + 1})")
        # region agent log
        _dbg(
            "H5",
            "dispatch_mastertune.py:_run_dispatch",
            "dispatch_item_start",
            {
                "seq": seq,
                "total_actionable": len(actionable),
                "mt_file": str(mt_file),
                "status": item.get("status", ""),
                "retries": int(item.get("retries", 0)),
            },
        )
        # endregion

        try:
            if item["status"] in (STATUS_PENDING, STATUS_EXPORTING):
                item["status"] = STATUS_EXPORTING
                item["updated_at"] = now
                _save_queue(queue_path, queue)

                err = _export_one_file(mt_file, axis_mode, window_title_re)
                if err:
                    # region agent log
                    _dbg(
                        "H5",
                        "dispatch_mastertune.py:_run_dispatch",
                        "export_error",
                        {"mt_file": str(mt_file), "error": err},
                    )
                    # endregion
                    item["retries"] += 1
                    item["reason"] = "export_failed"
                    item["message"] = err
                    if item["retries"] >= max_retries:
                        item["status"] = STATUS_FAILED
                        print(f"  FAILED (export, max retries): {err}")
                    else:
                        item["status"] = STATUS_PENDING
                        print(f"  export failed (will retry): {err}")
                    item["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _save_queue(queue_path, queue)
                    continue

                item["status"] = STATUS_EXPORTED
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_queue(queue_path, queue)
                print("  exported")

            if item["status"] == STATUS_EXPORTED:
                tsv = _tsv_paths(mt_file)
                if not all(_looks_filled(tsv[k]) for k in ("ve_front", "ve_rear", "lambda")):
                    item["status"] = STATUS_FAILED
                    item["reason"] = "tsv_unfilled"
                    item["message"] = "TSV files empty after export"
                    item["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _save_queue(queue_path, queue)
                    print("  FAILED (TSVs unfilled after export)")
                    continue

                err = _ingest_one(
                    mt_file,
                    library_dir,
                    queue_path,
                    idx,
                    str(item.get("status", "")),
                    int(item.get("retries", 0)),
                )
                if err:
                    item["retries"] += 1
                    item["reason"] = "ingest_failed"
                    item["message"] = err
                    if item["retries"] >= max_retries:
                        item["status"] = STATUS_FAILED
                        print(f"  FAILED (ingest, max retries): {err[:120]}")
                    else:
                        item["status"] = STATUS_EXPORTED
                        print(f"  ingest failed (will retry): {err[:120]}")
                    item["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _save_queue(queue_path, queue)
                    continue

                item["status"] = STATUS_INGESTED
                item["reason"] = ""
                item["message"] = ""
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_queue(queue_path, queue)
                print("  INGESTED")
        finally:
            if close_after_file:
                n = _close_mastertune_windows(window_title_re)
                if n:
                    print(f"  closed {n} MasterTune window(s)")

        if inter_file_delay > 0:
            _sleep_with_panic(inter_file_delay, "_run_dispatch:inter_file_delay")

    _print_summary(queue)


def _print_summary(queue: Dict[str, Any]) -> None:
    items = queue["items"]
    counts: Dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("\n" + "=" * 50)
    print("Dispatch summary")
    for status in (STATUS_INGESTED, STATUS_EXPORTED, STATUS_EXPORTING,
                   STATUS_PENDING, STATUS_FAILED, STATUS_SKIPPED):
        if counts.get(status, 0) > 0:
            print(f"  {status}: {counts[status]}")
    print(f"  total: {len(items)}")


# ── CLI ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Fully automated MasterTune ingest dispatcher"
    )
    parser.add_argument(
        "--calibration-dir", default=str(DEFAULT_CAL_DIR),
        help="Root directory containing MT files",
    )
    parser.add_argument("--library-dir", default=None)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument(
        "--file-contains", action="append", default=[],
        help="Filename filter (repeatable)",
    )
    parser.add_argument(
        "--axis-mode", choices=["map", "tps"], default="map",
        help="VE axis mode (no 'auto' in unattended mode)",
    )
    parser.add_argument(
        "--queue-path", default=str(DEFAULT_QUEUE_PATH),
        help="Path to persistent queue JSON",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from existing queue file instead of creating new one",
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max retry attempts per file before marking failed",
    )
    parser.add_argument(
        "--inter-file-delay", type=float, default=2.0,
        help="Seconds to wait between files",
    )
    parser.add_argument(
        "--window-title-re", default=r"MasterTune.*",
        help="Window title regex for pywinauto",
    )
    parser.add_argument(
        "--no-close-after-file", action="store_true",
        help="Do not WM_CLOSE MasterTune after each queue item (windows may pile up)",
    )
    args = parser.parse_args()

    queue_path = safe_path(args.queue_path, allow_parent_dir=True)

    if args.resume and queue_path.exists():
        print(f"Resuming from {queue_path}")
        queue = _load_queue(queue_path)
    else:
        cal_dir = safe_path(args.calibration_dir, allow_parent_dir=True)
        library_dir = (
            safe_path(args.library_dir, allow_parent_dir=True)
            if args.library_dir else None
        )
        queue = _build_queue(
            cal_dir, library_dir, args.axis_mode,
            args.max_files, list(args.file_contains),
        )
        _save_queue(queue_path, queue)
        print(f"Created queue with {len(queue['items'])} items -> {queue_path}")

    try:
        _run_dispatch(
            queue, queue_path, args.window_title_re,
            args.max_retries, args.inter_file_delay,
            close_after_file=not args.no_close_after_file,
        )
    except KeyboardInterrupt:
        _save_queue(queue_path, queue)
        print(f"\nInterrupted. Queue saved to {queue_path}")
        print("Resume with: python scripts/dispatch_mastertune.py --resume")
        _print_summary(queue)


if __name__ == "__main__":
    main()
