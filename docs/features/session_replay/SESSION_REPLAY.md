# Session Replay with Annotations

## Overview

The Session Replay feature provides complete transparency into every decision made during DynoAI tuning runs. It logs all actions, reasons, and values throughout the processing pipeline, enabling users to understand exactly what happened and why.

## Features

- **Complete Decision Logging**: Captures every significant decision during tuning
- **Timestamp Precision**: ISO 8601 timestamps with millisecond precision
- **Thread-Safe**: Uses locks to ensure safe concurrent access (<1% overhead)
- **Minimal Performance Impact**: Optimized logging with minimal overhead
- **Flexible Viewing**: Command-line viewer with filtering and export capabilities

## Architecture

### Session Log Structure

Each decision entry contains:
- `timestamp`: ISO 8601 timestamp (e.g., "2025-12-15T17:28:01.803Z")
- `action`: Action type (e.g., "AFR_CORRECTION", "SMOOTHING", "CLAMPING")
- `reason`: Human-readable explanation for the action
- `values`: Optional dictionary of before/after values
- `cell`: Optional cell location (RPM/KPA indices or bins)

### Logged Decision Points

1. **AFR Correction** (`AFR_CORRECTION`)
   - Logged for first 3 samples per bin
   - Includes: AFR error %, weight, commanded AFR, measured AFR
   - Cell location: RPM, KPA, cylinder

2. **Smoothing** (`SMOOTHING_START`, `GRADIENT_LIMITING`)
   - Start: Logs smoothing parameters (passes, threshold)
   - Gradient limiting: Logs when high gradients preserve original values
   - Includes: gradient magnitude, blend factors, original/smoothed/result values

3. **Clamping** (`CLAMPING_START`, `CLAMPING_APPLIED`)
   - Start: Logs clamping limit
   - Applied: Logs cells that were clamped with before/after values

4. **Anomaly Detection** (`ANOMALY_DETECTION_START`, `ANOMALY_DETECTED`)
   - Start: Marks beginning of anomaly analysis
   - Detected: Logs each anomaly with type, score, and explanation

## Usage

### Automatic Generation

Session replay logs are automatically generated during every tuning run and saved as `session_replay.json` in the output directory.

```bash
python ai_tuner_toolkit_dyno_v1_2.py --csv data.csv --outdir output/
# Creates: output/session_replay.json
```

### Viewing Session Logs

Use the `replay_viewer.py` tool to view and analyze session logs:

#### Show Summary Statistics

```bash
python replay_viewer.py output/session_replay.json --summary-only
```

Output:
```
======================================================================
SESSION REPLAY SUMMARY
======================================================================
Run ID:          2025-12-15T17-28-01Z-e46826
Generated:       2025-12-15T17:28:01.830Z
Total Decisions: 119
Duration:        22.0ms

DECISIONS BY ACTION TYPE:
  AFR_CORRECTION                    98
  GRADIENT_LIMITING                 18
  SMOOTHING_START                    1
  CLAMPING_START                     1
  ANOMALY_DETECTION_START            1
======================================================================
```

#### View Full Timeline

```bash
python replay_viewer.py output/session_replay.json
```

Shows all decisions with timestamps, actions, reasons, and values.

#### Filter by Action Type

```bash
python replay_viewer.py output/session_replay.json --action SMOOTHING
python replay_viewer.py output/session_replay.json --action AFR_CORRECTION --limit 10
python replay_viewer.py output/session_replay.json --action GRADIENT
```

#### Export to File

```bash
python replay_viewer.py output/session_replay.json --action GRADIENT --export gradient_log.txt
```

## File Format

### session_replay.json Structure

```json
{
  "schema_version": "1.0",
  "run_id": "2025-12-15T17-28-01Z-e46826",
  "generated_at": "2025-12-15T17:28:01.830Z",
  "total_decisions": 119,
  "decisions": [
    {
      "timestamp": "2025-12-15T17:28:01.803Z",
      "action": "AFR_CORRECTION",
      "reason": "Accepted AFR error sample for f cylinder",
      "values": {
        "afr_error_pct": 0.73,
        "weight": 73.3,
        "afr_commanded": 12.5,
        "afr_measured": 12.41
      },
      "cell": {
        "rpm": 2000,
        "kpa": 65,
        "cylinder": "f"
      }
    }
  ]
}
```

## Integration with Manifest

Session replay logs are automatically registered in the manifest:

```json
{
  "outputs": [
    {
      "name": "session_replay.json",
      "path": "session_replay.json",
      "type": "json",
      "schema": "session_replay",
      "size_bytes": 48169,
      "sha256": "37524618cc83458365496da9e4b45e8201cda6d42d837c8ed2f0698dc4cbbc64",
      "created": "2025-12-15T17:28:01.889Z"
    }
  ]
}
```

## API Reference

### log_decision()

```python
def log_decision(
    action: str,
    reason: str,
    values: Optional[Dict[str, Any]] = None,
    cell: Optional[Dict[str, int]] = None,
) -> None:
    """Log a decision made during processing for session replay.

    Args:
        action: Action performed (e.g., "AFR_CORRECTION", "SMOOTHING")
        reason: Reason for the action
        values: Optional dict of values involved (before/after)
        cell: Optional cell location (rpm, kpa indices)
    """
```

### get_session_log()

```python
def get_session_log() -> List[Dict[str, Any]]:
    """Get a copy of the current session log (thread-safe)."""
```

### clear_session_log()

```python
def clear_session_log() -> None:
    """Clear the session log (thread-safe)."""
```

### write_session_replay()

```python
def write_session_replay(outdir: str | Path, run_id: str) -> None:
    """Write session replay log to JSON file.

    Args:
        outdir: Output directory path
        run_id: Run identifier for the session
    """
```

## Performance Characteristics

- **Logging Overhead**: <1% of total processing time
- **Thread Safety**: Uses threading.Lock for concurrent access
- **Memory Footprint**: ~400 bytes per decision entry
- **Typical Session**: 100-200 decisions, ~50KB file size

## Use Cases

### 1. Debugging Unexpected Results

When tuning results are unexpected, use session replay to:
- Identify which cells were clamped
- See which corrections were limited by gradient thresholds
- Trace AFR error calculations

```bash
python replay_viewer.py output/session_replay.json --action CLAMPING
```

### 2. Understanding Smoothing Behavior

Review how smoothing affected specific cells:

```bash
python replay_viewer.py output/session_replay.json --action GRADIENT
```

### 3. Audit Trail for Production

Export complete decision log for compliance:

```bash
python replay_viewer.py output/session_replay.json --export audit_trail.txt
```

### 4. Comparing Runs

Compare decision counts and timings across different runs:

```bash
python replay_viewer.py run1/session_replay.json --summary-only
python replay_viewer.py run2/session_replay.json --summary-only
```

## Security Considerations

- All file operations use `io_contracts.safe_path()` for path validation
- Thread-safe logging prevents race conditions
- No sensitive data (passwords, keys) is logged
- SHA-256 checksums in manifest ensure file integrity

## Future Enhancements

Potential improvements for future versions:

1. **Visual Timeline**: Web-based interactive timeline viewer
2. **Diff Tool**: Compare decisions between two runs
3. **Decision Playback**: Step-by-step replay with state visualization
4. **Custom Filters**: Filter by cell location, value ranges, time windows
5. **Export Formats**: CSV, HTML, PDF export options
6. **Performance Metrics**: Per-decision timing and resource usage

## Troubleshooting

### Session Log Not Created

**Problem**: `session_replay.json` is missing from output directory.

**Solution**: Check that the tuning run completed successfully. The session log is written at the end of processing.

### Empty Decision Log

**Problem**: Session log exists but contains no decisions.

**Solution**: Verify that logging calls are being executed. Check for errors in the processing pipeline.

### Large File Size

**Problem**: Session replay file is larger than expected.

**Solution**: This is normal for runs with many cells and high coverage. Consider filtering to specific actions when viewing.

### Timestamp Parsing Errors

**Problem**: Replay viewer fails to parse timestamps.

**Solution**: Ensure the session replay file is valid JSON and uses ISO 8601 format. Check for file corruption.

## Examples

### Example 1: View AFR Corrections for a Specific Cell

```bash
# View all AFR corrections
python replay_viewer.py output/session_replay.json --action AFR_CORRECTION | grep "RPM=2000 KPA=65"
```

### Example 2: Count Gradient Limiting Events

```bash
python replay_viewer.py output/session_replay.json --action GRADIENT --summary-only
```

### Example 3: Export Full Timeline

```bash
python replay_viewer.py output/session_replay.json --export full_timeline.txt
```

### Example 4: Find Clamped Cells

```bash
python replay_viewer.py output/session_replay.json --action CLAMPING_APPLIED
```

## Conclusion

Session Replay provides complete transparency into DynoAI's decision-making process, enabling users to understand, debug, and audit every tuning run. The combination of automatic logging, flexible viewing, and minimal performance impact makes it an essential tool for professional tuning workflows.

