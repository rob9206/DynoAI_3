"""List newest files in Ryan Titus watch folder."""

import datetime as dt
from pathlib import Path

D = Path(r"C:\Users\dawso\OneDrive\Desktop\fat boy\fatboy cvo\2006\ryan titus")

files = sorted(
    [p for p in D.iterdir() if p.suffix.lower() in (".txt", ".wp8")],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
print(f"folder: {D}")
print(f"total files: {len(files)}")
print()
for p in files[:20]:
    print(
        dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        p.name,
        p.stat().st_size,
    )
