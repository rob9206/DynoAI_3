"""
Probe registered TTS COM classes and print candidate automation interfaces.
"""

from __future__ import annotations

import argparse
import json
import platform
import winreg
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _enum_subkeys(root: int, path: str) -> Iterable[str]:
    try:
        key = winreg.OpenKey(root, path)
    except OSError:
        return []
    names: List[str] = []
    idx = 0
    while True:
        try:
            names.append(winreg.EnumKey(key, idx))
            idx += 1
        except OSError:
            break
    winreg.CloseKey(key)
    return names


def _get_default_value(root: int, path: str) -> Optional[str]:
    try:
        key = winreg.OpenKey(root, path)
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        return str(value)
    except OSError:
        return None


def _scan_progids(prefixes: Tuple[str, ...]) -> List[Dict[str, Any]]:
    progid_entries: List[Dict[str, Any]] = []
    for progid in _enum_subkeys(winreg.HKEY_CLASSES_ROOT, ""):
        progid_upper = progid.upper()
        if not any(progid_upper.startswith(prefix) for prefix in prefixes):
            continue
        clsid = _get_default_value(winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID")
        local_server = _get_default_value(
            winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID\\LocalServer32"
        )
        inproc_server = _get_default_value(
            winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID\\InprocServer32"
        )
        progid_entries.append(
            {
                "progid": progid,
                "clsid": clsid or "",
                "local_server": local_server or "",
                "inproc_server": inproc_server or "",
            }
        )
    return sorted(progid_entries, key=lambda row: row["progid"].lower())


def _try_dispatch(progid: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"progid": progid, "dispatch_ok": False, "error": ""}
    try:
        import win32com.client as win32_client  # type: ignore[import-untyped]

        obj = win32_client.Dispatch(progid)
        method_names = [
            name
            for name in dir(obj)
            if not name.startswith("_") and callable(getattr(obj, name, None))
        ]
        result["dispatch_ok"] = True
        result["method_count"] = len(method_names)
        result["sample_methods"] = method_names[:25]
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe TTS COM interfaces")
    parser.add_argument(
        "--prefix",
        action="append",
        default=["TTS.", "Tts."],
        help="ProgID prefix to search (default: TTS., Tts.)",
    )
    parser.add_argument(
        "--try-dispatch",
        action="store_true",
        help="Attempt win32com Dispatch for discovered ProgIDs",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON payload instead of plain text",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    prefixes = tuple(prefix.upper() for prefix in args.prefix)

    discovered = _scan_progids(prefixes=prefixes)
    dispatch_results: List[Dict[str, Any]] = []
    if args.try_dispatch:
        for row in discovered:
            dispatch_results.append(_try_dispatch(row["progid"]))

    payload = {
        "platform": platform.platform(),
        "prefixes": list(prefixes),
        "count": len(discovered),
        "progids": discovered,
        "dispatch": dispatch_results,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print("TTS COM probe complete")
    print(f"- prefixes: {', '.join(args.prefix)}")
    print(f"- progids found: {len(discovered)}")
    for row in discovered:
        print(f"  - {row['progid']}")
        if row["local_server"]:
            print(f"      local_server: {row['local_server']}")
        if row["inproc_server"]:
            print(f"      inproc_server: {row['inproc_server']}")
    if dispatch_results:
        print("\nDispatch results:")
        for row in dispatch_results:
            status = "ok" if row["dispatch_ok"] else "failed"
            print(f"  - {row['progid']}: {status}")
            if row["dispatch_ok"]:
                print(f"      methods: {row.get('method_count', 0)}")
            else:
                print(f"      error: {row['error']}")


if __name__ == "__main__":
    main()
