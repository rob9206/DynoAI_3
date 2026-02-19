#!/usr/bin/env python3
"""
Re-run the DynoAI bug scan: security tools + pattern checks for known issues.

Usage:
  python scripts/dev/run_bug_scan.py
  python scripts/dev/run_bug_scan.py --output BUG_SCAN_REPORT.md

Runs:
  - bandit (Python security)
  - safety (dependency vulnerabilities)
  - Pattern checks for issues from BUG_SCAN_REPORT.md
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root (parent of scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


def run_cmd(cmd: list[str], cwd: Path | None = None, capture: bool = True) -> tuple[int, str]:
    """Run command; return (returncode, combined stdout+stderr)."""
    cwd = cwd or REPO_ROOT
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=capture,
            text=True,
            timeout=120,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out
    except FileNotFoundError:
        return -1, f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "Command timed out (120s)"


def check_pattern(path: Path, pattern: str, description: str) -> list[tuple[int, str]]:
    """Return list of (line_no, line_content) where pattern matches."""
    if not path.exists():
        return []
    hits = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line):
            hits.append((i, line.strip()[:120]))
    return hits


def main() -> int:
    output_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])
    if output_path and not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def out(s: str = "") -> None:
        lines.append(s)
        print(s)

    out("# DynoAI Bug Scan Report")
    out("")
    out(f"**Generated:** {now}")
    out("**Scope:** Backend (api, dynoai), frontend patterns, security tools")
    out("")
    out("---")
    out("")

    # --- Bandit ---
    out("## 1. Bandit (Python security)")
    out("")
    code, bandit_out = run_cmd(
        [sys.executable, "-m", "bandit", "-r", "api", "dynoai", "-ll", "--skip", "B101", "-f", "txt"],
        cwd=REPO_ROOT,
    )
    if code == -1:
        out("Bandit not run or failed:")
        out("```")
        out(bandit_out or " (no output)")
        out("```")
    else:
        out("```")
        out(bandit_out[:8000] if len(bandit_out) > 8000 else bandit_out)
        if len(bandit_out) > 8000:
            out("... (truncated)")
        out("```")
    out("")

    # --- Safety ---
    out("## 2. Safety (dependency vulnerabilities)")
    out("")
    req = REPO_ROOT / "requirements.txt"
    if req.exists():
        code2, safety_out = run_cmd(
            [sys.executable, "-m", "safety", "check", "-r", "requirements.txt"],
            cwd=REPO_ROOT,
        )
        out("```")
        out(safety_out[:6000] if safety_out else "No output (safety may not be installed: pip install safety)")
        if safety_out and len(safety_out) > 6000:
            out("... (truncated)")
        out("```")
    else:
        out("No requirements.txt found.")
    out("")

    # --- Known-issue pattern checks ---
    out("## 3. Known-issue pattern checks")
    out("")
    out("Checks for patterns from BUG_SCAN_REPORT (critical/high).")
    out("")

    checks = [
        ("api/app.py", r"os\.chdir\s*\(", "Global CWD mutation (concurrent request risk)"),
        ("api/app.py", r"elif\s*\(\s*__name__\s*==\s*[\"']api\.app[\"']", "Import-time server start (WSGI risk)"),
        ("api/app.py", r"print_startup_banner\s*\(\s*\)", "Startup banner / app.run() call"),
        ("api/routes/wizards.py", r"output_dir\s*=\s*OUTPUT_FOLDER\s*/\s*output_id", "Path traversal (run_id in path)"),
        ("api/routes/reports.py", r"@reports_bp\.route.*branding.*PUT", "Unauthenticated branding write"),
        ("api/routes/jetstream/config.py", r"mask_key\s*=\s*False", "Credential persistence (plaintext key)"),
        ("frontend/src/lib/api.ts", r"confidence-report", "Frontend confidence-report path (404 if backend is /api/confidence/)"),
        ("dynoai/core/ve_operations.py", r"/\s*multiplier", "Divide-by-zero risk in rollback"),
        ("api/app.py", r"subprocess\.run\s*\([^)]*\)", "Subprocess timeout missing"),
    ]

    for file_spec, pattern, desc in checks:
        path = REPO_ROOT / file_spec
        hits = check_pattern(path, pattern, desc)
        if hits:
            out(f"- **{file_spec}**: {desc}")
            for ln, content in hits[:5]:
                out(f"  - L{ln}: `{content}`")
            if len(hits) > 5:
                out(f"  - ... and {len(hits) - 5} more")
            out("")
        else:
            out(f"- **{file_spec}**: No match for pattern (may be fixed or refactored).")
            out("")

    out("---")
    out("")
    out("## How to run this scan")
    out("")
    out("```bash")
    out("pip install bandit safety  # if not already installed")
    out("python scripts/dev/run_bug_scan.py")
    out("python scripts/dev/run_bug_scan.py --output BUG_SCAN_REPORT.md")
    out("```")
    out("")

    if output_path:
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote report to {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
