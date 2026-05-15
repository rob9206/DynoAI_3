"""One-shot diagnostic: list channels from WP8 files the user pointed to.

Bypasses the path-restriction in parse_wp8_file by calling the lower-level
_parse_channel_def scan directly so we can read files from Downloads.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.services.parsers.wp8_parser import WP8_MAGIC, _parse_channel_def


def list_channels(wp8_path: Path) -> list[str]:
    data = wp8_path.read_bytes()
    if data[:4] != WP8_MAGIC:
        return [f"<invalid magic: {data[:4].hex()}>"]

    content = data[4:]
    seen: list[str] = []
    i = 0
    while i < len(content) - 10:
        if content[i] == 0x0A:
            try:
                msg_len = content[i + 1]
                if 5 < msg_len < 200 and i + 2 + msg_len <= len(content):
                    msg_data = content[i + 2 : i + 2 + msg_len]
                    channel = _parse_channel_def(msg_data)
                    if channel and channel.name and channel.name not in seen:
                        seen.append(channel.name)
                    i += 2 + msg_len
                    continue
            except (IndexError, ValueError):
                pass
        i += 1
    return seen


def main() -> int:
    out_path = Path(__file__).parent / "_wp8_channels.txt"
    paths = [Path(p) for p in sys.argv[1:]]
    lines: list[str] = []
    for p in paths:
        lines.append(f"\n=== {p.name} ({p.stat().st_size/1024:.1f} KB) ===")
        channels = list_channels(p)
        lines.append(f"  {len(channels)} channels")

        afr_like = [c for c in channels if any(tok in c.lower() for tok in ("afr", "lambda", "wbo2", "wideband"))]
        lines.append(f"  AFR/lambda-like channels ({len(afr_like)}):")
        for name in afr_like:
            lines.append(f"    * {name}")

        lines.append(f"  All channels:")
        for name in channels:
            lines.append(f"    - {name}")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
