# Session Replay Quick Reference

## What is Session Replay?

Session Replay logs every decision made during DynoAI tuning runs, providing complete transparency into the processing pipeline.

## Quick Start

### 1. Run Tuning (Automatic Logging)

```bash
python ai_tuner_toolkit_dyno_v1_2.py --csv data.csv --outdir output/
```

Session replay is automatically saved to `output/session_replay.json`

### 2. View Session Summary

```bash
python replay_viewer.py output/session_replay.json --summary-only
```

### 3. View Full Timeline

```bash
python replay_viewer.py output/session_replay.json
```

## Common Commands

### Filter by Action Type

```bash
# View smoothing decisions
python replay_viewer.py output/session_replay.json --action SMOOTHING

# View AFR corrections
python replay_viewer.py output/session_replay.json --action AFR_CORRECTION

# View gradient limiting
python replay_viewer.py output/session_replay.json --action GRADIENT

# View clamping
python replay_viewer.py output/session_replay.json --action CLAMPING

# View anomalies
python replay_viewer.py output/session_replay.json --action ANOMALY
```

### Limit Results

```bash
# Show first 10 decisions
python replay_viewer.py output/session_replay.json --limit 10

# Show first 5 AFR corrections
python replay_viewer.py output/session_replay.json --action AFR_CORRECTION --limit 5
```

### Export to File

```bash
# Export all decisions
python replay_viewer.py output/session_replay.json --export timeline.txt

# Export specific action type
python replay_viewer.py output/session_replay.json --action GRADIENT --export gradient_log.txt
```

## Decision Types

| Action | Description | Key Values |
|--------|-------------|------------|
| `AFR_CORRECTION` | AFR error sample accepted | afr_error_pct, weight, afr_commanded, afr_measured |
| `SMOOTHING_START` | Smoothing begins | passes, gradient_threshold |
| `GRADIENT_LIMITING` | High gradient detected | gradient, blend_factor, original, smoothed, result |
| `CLAMPING_START` | Clamping begins | limit |
| `CLAMPING_APPLIED` | Values clamped | clamped_count, cells |
| `ANOMALY_DETECTION_START` | Anomaly analysis begins | - |
| `ANOMALY_DETECTED` | Anomaly found | type, score |

## Example Output

```
[1] 2025-12-15T17:28:01.803Z (+0.0ms)
  ACTION: AFR_CORRECTION
  REASON: Accepted AFR error sample for f cylinder
  CELL:   RPM=2000 KPA=65 Cyl=f
  VALUES:
    afr_error_pct: 0.730
    weight: 73.300
    afr_commanded: 12.500
    afr_measured: 12.410
```

## File Location

Session replay logs are saved in the output directory:

```
output/
├── session_replay.json          ← Session log
├── manifest.json                 ← References session log
├── VE_Correction_Delta_DYNO.csv
└── ... (other outputs)
```

## Troubleshooting

### Log not created?
- Check that tuning completed successfully
- Verify output directory exists

### Empty log?
- Check for errors in processing pipeline
- Verify data was processed

### Can't view log?
- Ensure `replay_viewer.py` is in the same directory as the toolkit
- Check that `session_replay.json` is valid JSON

## Performance

- **Overhead**: <1% of total processing time
- **File Size**: ~400-500 bytes per decision
- **Typical Session**: 100-200 decisions, ~50KB

## Documentation

Full documentation: `docs/SESSION_REPLAY.md`

## Support

For issues or questions, refer to the full documentation or check the implementation summary in `SESSION_REPLAY_IMPLEMENTATION.md`.

