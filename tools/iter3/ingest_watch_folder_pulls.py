"""Copy new OneDrive watch-folder pulls into iter_N/pulls and update manifest.

Default target is the currently flashed iteration. Pass --iter N to override
(useful for backfilling baseline pulls into iter_2 after the fact).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

WATCH_FOLDER = Path(
    r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus"
)
SESSION_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
)
DEFAULT_ITER = 3


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iter",
        dest="iter_n",
        type=int,
        default=DEFAULT_ITER,
        help=f"Target iteration index (default: {DEFAULT_ITER})",
    )
    args = parser.parse_args()

    pulls_dir = SESSION_DIR / "iterations" / f"iter_{args.iter_n}" / "pulls"
    wp8_dir = pulls_dir / "raw_wp8"
    manifest_path = pulls_dir / "manifest.json"

    pulls_dir.mkdir(parents=True, exist_ok=True)
    wp8_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict = {}
    known_names: set[str] = set()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        known_names = {x["name"] for x in manifest.get("pulls", [])}
        known_names |= {x["name"] for x in manifest.get("sources", [])}

    candidates = sorted(
        [
            p
            for p in WATCH_FOLDER.iterdir()
            if p.suffix.lower() in (".txt", ".wp8")
        ],
        key=lambda p: p.stat().st_mtime,
    )

    pulls_key = "pulls" if "pulls" in manifest or not manifest.get("sources") else "sources"

    added: list[dict] = []
    for src in candidates:
        if src.name in known_names:
            continue
        dest = wp8_dir / src.name if src.suffix.lower() == ".wp8" else pulls_dir / src.name
        shutil.copy2(src, dest)
        rec = {
            "name": src.name,
            "sha256": sha256(src),
            "bytes": src.stat().st_size,
            "mtime": dt.datetime.fromtimestamp(src.stat().st_mtime).isoformat(
                timespec="seconds"
            ),
        }
        manifest.setdefault(pulls_key, []).append(rec)
        known_names.add(src.name)
        added.append(rec)

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"target: iter_{args.iter_n} -> {pulls_dir}")
    print(f"added files: {len(added)}")
    for rec in added:
        print(f"  {rec['name']}  {rec['bytes']} bytes  {rec['sha256'][:12]}...")
    print(f"manifest total {pulls_key}: {len(manifest.get(pulls_key, []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
