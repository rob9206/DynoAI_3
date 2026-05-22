"""Remove iter_4/pulls files whose SHA matches any iter_3/pulls file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

SESSION_DIR = Path(
    r"c:\Dev\DynoAI_3\vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline"
)
ITER3_PULLS = SESSION_DIR / "iterations" / "iter_3" / "pulls"
ITER4_PULLS = SESSION_DIR / "iterations" / "iter_4" / "pulls"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    iter3_shas = {
        sha(p) for p in ITER3_PULLS.rglob("*") if p.is_file() and p.suffix.lower() in (".txt", ".wp8")
    }
    removed: list[str] = []
    for p in list(ITER4_PULLS.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".txt", ".wp8"):
            continue
        if sha(p) in iter3_shas:
            p.unlink()
            removed.append(p.name)

    manifest_path = ITER4_PULLS / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pulls = manifest.get("pulls", [])
        pulls = [rec for rec in pulls if rec["name"] not in removed]
        manifest["pulls"] = pulls
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"removed {len(removed)} duplicates from iter_4/pulls")
    for r in removed:
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
