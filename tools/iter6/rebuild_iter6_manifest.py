"""Clean up iter_6/pulls so it only contains true iter_6 pulls.

iter_6 was flashed on 2026-05-12 between roughly 17:50 and 18:20 (local).
Pulls _25..28 are post-flash but with a dragging rear brake (INVALID).
Pulls _31..33 are post-flash, post-brake-fix (VALID).
Everything else is a leak from earlier iterations and gets removed.

Re-runnable. Idempotent.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

ITER_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
    r"\iterations\iter_6"
)
PULLS_DIR = ITER_DIR / "pulls"
WP8_DIR = PULLS_DIR / "raw_wp8"
MANIFEST = PULLS_DIR / "manifest.json"
WATCH = Path(
    r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus"
)

KEEP_INDICES = [25, 26, 27, 28, 31, 32, 33]
INVALID_INDICES = {25, 26, 27, 28}
INVALID_REASON = "rear_brake_dragging_loaded_pull"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    keep_names = {f"PV_Logfile_5.csv_{i}.txt" for i in KEEP_INDICES}

    PULLS_DIR.mkdir(parents=True, exist_ok=True)
    WP8_DIR.mkdir(parents=True, exist_ok=True)

    removed: list[str] = []
    for p in PULLS_DIR.iterdir():
        if p.is_dir():
            continue
        if p.name == "manifest.json":
            continue
        if p.name not in keep_names:
            p.unlink()
            removed.append(p.name)

    if WP8_DIR.exists():
        for p in WP8_DIR.iterdir():
            if p.is_file():
                p.unlink()
                removed.append(f"raw_wp8/{p.name}")

    pulls: list[dict] = []
    for i in KEEP_INDICES:
        name = f"PV_Logfile_5.csv_{i}.txt"
        local = PULLS_DIR / name
        if not local.exists():
            src = WATCH / name
            if src.exists():
                shutil.copy2(src, local)
            else:
                print(f"WARN: missing {name} in both iter_6/pulls and watch folder")
                continue
        rec = {
            "name": name,
            "sha256": sha256(local),
            "bytes": local.stat().st_size,
            "mtime": dt.datetime.fromtimestamp(local.stat().st_mtime).isoformat(timespec="seconds"),
            "valid": i not in INVALID_INDICES,
        }
        if i in INVALID_INDICES:
            rec["invalid_reason"] = INVALID_REASON
        pulls.append(rec)

    manifest = {
        "iteration_id": "iter_6",
        "tune_state": "iter_6_patched.pvv",
        "tune_sha256": "fd5ba039839ef3cc2c1608d963f388927c0172c7d843aa38bd04e2ec0bd1a5ff",
        "afr_source": "dyno_tailpipe_wideband_only",
        "wideband_channel": "LC2 (Innovate venturi in collector)",
        "lc1_status": "not_hooked_up_ignore",
        "test_mode": "loaded_4th_gear_wot",
        "notes": [
            "Pulls _25..28 captured with a DRAGGING REAR BRAKE; treat as load-test data, NOT free-accel WOT.",
            "Pulls _31..33 captured AFTER brake fix; these are the valid iter_6 post-flash WOT pulls.",
        ],
        "pulls": pulls,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"removed {len(removed)} stray files")
    print(f"kept {len(pulls)} pulls in iter_6/pulls")
    for r in pulls:
        flag = "VALID  " if r["valid"] else "INVALID"
        print(f"  {flag}  {r['name']}  {r['bytes']:>7d}  sha={r['sha256'][:12]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
