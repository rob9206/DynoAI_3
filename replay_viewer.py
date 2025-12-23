#!/usr/bin/env python3
"""
Session Replay Viewer for DynoAI

Reads session_replay.json and displays a timeline of all decisions made during tuning.
Shows timestamps, actions, reasons, and values for complete transparency.

Usage:
    python replay_viewer.py <path_to_session_replay.json>
    python replay_viewer.py <path_to_session_replay.json> --action SMOOTHING
    python replay_viewer.py <path_to_session_replay.json> --export timeline.txt
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp to datetime object."""
    # Handle both Z and +00:00 suffixes
    ts_clean = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts_clean)


def format_duration(start_ts: str, end_ts: str) -> str:
    """Calculate and format duration between two timestamps."""
    start = parse_timestamp(start_ts)
    end = parse_timestamp(end_ts)
    delta = end - start
    ms = delta.total_seconds() * 1000
    if ms < 1000:
        return f"{ms:.1f}ms"
    else:
        return f"{ms/1000:.2f}s"


def format_cell(cell: Optional[Dict[str, Any]]) -> str:
    """Format cell location for display."""
    if not cell:
        return ""
    
    parts = []
    if "rpm" in cell:
        parts.append(f"RPM={cell['rpm']}")
    if "kpa" in cell:
        parts.append(f"KPA={cell['kpa']}")
    if "rpm_index" in cell:
        parts.append(f"RPM[{cell['rpm_index']}]")
    if "kpa_index" in cell:
        parts.append(f"KPA[{cell['kpa_index']}]")
    if "cylinder" in cell:
        parts.append(f"Cyl={cell['cylinder']}")
    
    return " ".join(parts) if parts else str(cell)


def format_values(values: Optional[Dict[str, Any]], indent: int = 4) -> str:
    """Format values dictionary for display."""
    if not values:
        return ""
    
    lines = []
    prefix = " " * indent
    
    for key, value in values.items():
        if isinstance(value, (int, float)):
            if isinstance(value, float):
                lines.append(f"{prefix}{key}: {value:.3f}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, list) and len(value) > 5:
            # Truncate long lists
            lines.append(f"{prefix}{key}: [{len(value)} items, showing first 3]")
            for item in value[:3]:
                lines.append(f"{prefix}  - {item}")
        elif isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            for k, v in value.items():
                lines.append(f"{prefix}  {k}: {v}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    
    return "\n".join(lines)


def display_decision(decision: Dict[str, Any], index: int, start_time: Optional[str] = None) -> str:
    """Format a single decision for display."""
    lines = []
    
    # Header with index and timestamp
    ts = decision.get("timestamp", "")
    if start_time:
        elapsed = format_duration(start_time, ts)
        lines.append(f"\n[{index}] {ts} (+{elapsed})")
    else:
        lines.append(f"\n[{index}] {ts}")
    
    # Action
    action = decision.get("action", "UNKNOWN")
    lines.append(f"  ACTION: {action}")
    
    # Reason
    reason = decision.get("reason", "")
    if reason:
        lines.append(f"  REASON: {reason}")
    
    # Cell location
    cell = decision.get("cell")
    if cell:
        lines.append(f"  CELL:   {format_cell(cell)}")
    
    # Values
    values = decision.get("values")
    if values:
        lines.append("  VALUES:")
        lines.append(format_values(values))
    
    return "\n".join(lines)


def filter_decisions(
    decisions: List[Dict[str, Any]], 
    action_filter: Optional[str] = None,
    cell_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Filter decisions by action type or cell location."""
    filtered = decisions
    
    if action_filter:
        action_upper = action_filter.upper()
        filtered = [d for d in filtered if action_upper in d.get("action", "").upper()]
    
    if cell_filter:
        filtered = [
            d for d in filtered 
            if d.get("cell") and all(
                d["cell"].get(k) == v for k, v in cell_filter.items()
            )
        ]
    
    return filtered


def generate_summary(replay_data: Dict[str, Any]) -> str:
    """Generate summary statistics for the session."""
    decisions = replay_data.get("decisions", [])
    
    if not decisions:
        return "No decisions logged in this session."
    
    # Count by action type
    action_counts: Dict[str, int] = {}
    for decision in decisions:
        action = decision.get("action", "UNKNOWN")
        action_counts[action] = action_counts.get(action, 0) + 1
    
    # Calculate duration
    first_ts = decisions[0].get("timestamp", "")
    last_ts = decisions[-1].get("timestamp", "")
    duration = format_duration(first_ts, last_ts) if first_ts and last_ts else "N/A"
    
    lines = [
        "=" * 70,
        "SESSION REPLAY SUMMARY",
        "=" * 70,
        f"Run ID:          {replay_data.get('run_id', 'N/A')}",
        f"Generated:       {replay_data.get('generated_at', 'N/A')}",
        f"Total Decisions: {len(decisions)}",
        f"Duration:        {duration}",
        "",
        "DECISIONS BY ACTION TYPE:",
    ]
    
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {action:30s} {count:5d}")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)


def display_timeline(
    replay_data: Dict[str, Any],
    action_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> str:
    """Display full timeline of decisions."""
    decisions = replay_data.get("decisions", [])
    
    if action_filter:
        decisions = filter_decisions(decisions, action_filter=action_filter)
    
    if not decisions:
        return "No decisions match the filter criteria."
    
    if limit:
        decisions = decisions[:limit]
    
    lines = [generate_summary(replay_data), ""]
    
    start_time = decisions[0].get("timestamp") if decisions else None
    
    for idx, decision in enumerate(decisions, 1):
        lines.append(display_decision(decision, idx, start_time))
    
    if limit and len(replay_data.get("decisions", [])) > limit:
        remaining = len(replay_data["decisions"]) - limit
        lines.append(f"\n... and {remaining} more decisions (use --limit to see more)")
    
    return "\n".join(lines)


def export_timeline(
    replay_data: Dict[str, Any],
    output_path: str,
    action_filter: Optional[str] = None,
) -> None:
    """Export timeline to a text file."""
    timeline = display_timeline(replay_data, action_filter=action_filter)
    
    output = Path(output_path)
    output.write_text(timeline, encoding="utf-8")
    
    print(f"Timeline exported to: {output_path}")


def main() -> int:
    """Main entry point for replay viewer."""
    parser = argparse.ArgumentParser(
        description="View DynoAI session replay logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "replay_file",
        help="Path to session_replay.json file",
    )
    
    parser.add_argument(
        "--action",
        help="Filter by action type (e.g., SMOOTHING, CLAMPING, AFR_CORRECTION)",
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of decisions to display",
    )
    
    parser.add_argument(
        "--export",
        help="Export timeline to specified file",
    )
    
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Show only summary statistics",
    )
    
    args = parser.parse_args()
    
    # Load replay file
    replay_path = Path(args.replay_file)
    if not replay_path.exists():
        print(f"ERROR: Replay file not found: {args.replay_file}", file=sys.stderr)
        return 1
    
    try:
        with open(replay_path, "r", encoding="utf-8") as f:
            replay_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in replay file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: Failed to read replay file: {e}", file=sys.stderr)
        return 1
    
    # Validate schema
    if "decisions" not in replay_data:
        print("ERROR: Invalid replay file format (missing 'decisions' key)", file=sys.stderr)
        return 1
    
    # Display or export
    if args.export:
        export_timeline(replay_data, args.export, action_filter=args.action)
    elif args.summary_only:
        print(generate_summary(replay_data))
    else:
        timeline = display_timeline(
            replay_data, 
            action_filter=args.action,
            limit=args.limit,
        )
        print(timeline)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

