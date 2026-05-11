# DynoAI ↔ Power Core Bridge

This folder contains a TuneLab/IronPython script that lets you trigger the
DynoAI synthetic WinPEP generator directly from inside **Dynojet Power Core**.

## Files

| File | Purpose |
| --- | --- |
| `dynoai_tunelab_bridge.py` | WinForms-based TuneLab script. Auto-detects peak RPM from the most recently loaded log, then shells out to `python -m tools.synthetic.winpep8_cli` inside your DynoAI repo. |
| `dynoai_preflight.py` | TuneLab pre-flight safety checker (battery/AFR/engine temp/intake temp) before a dyno pull. |
| `dynoai_autotune.py` | TuneLab per-cylinder autotune script. Exports loaded log channels to temp CSV, runs `python -m tools.autotune.tunelab_entrypoint preview`, and supports both Export and F1.1 live-tune apply in dual-cylinder mode. |
| `inspect_tunelab_context.py` | Throwaway TuneLab probe script that dumps `dir(context)` and tests candidate VE table names so you can confirm table API behavior in a specific Power Core build. |

## Installation Steps

1. **Edit Script Defaults (optional)**  
   Update `DEFAULT_REPO_ROOT` / `DEFAULT_PYTHON` near the top of
   `dynoai_tunelab_bridge.py` if your DynoAI checkout or virtualenv lives
   elsewhere.

2. **Leave the script where it is**  
   The script can live anywhere readable — we recommend leaving it in the repo
   at `api/services/integrations/powercore/dynoai_tunelab_bridge.py`. TuneLab
   does **not** scan any directory automatically; you explicitly register the
   file in the next step, and Power Core will load it from that path on every
   launch.

3. **Register with TuneLab**  
   Launch Power Core → Tools → TuneLab → Manage Scripts → *Add* → browse to
   the script and pick it. `DynoAIWinPEPBridge` will then appear in the
   TuneLab Scripts list.

4. **Configure DynoAI environment**  
   Ensure your DynoAI repo (`DEFAULT_REPO_ROOT`) is accessible and that running
   the CLI manually works:

   ```powershell
   cd C:\Dev\DynoAI_3
   python -m tools.synthetic.winpep8_cli --help
   ```

## Usage

1. In Power Core Data Center, load the log (or logs) you want. RPM will be
   auto-detected from the most recently loaded file.
2. Run the `DynoAIWinPEPBridge` TuneLab script.
3. The dialog pre-fills `HP Peak RPM` and `TQ Peak RPM` from the detected
   peak RPM. Enter Peak HP and Peak TQ manually (values you read off the
   dyno chart you're synthesizing).
4. Click **Generate**. The script calls DynoAI, writes
   `runs/<run_id>/run.csv`, and shows a success dialog with an **Open Folder**
   shortcut. Import the CSV into WinPEP / Control Center as usual.

## Pre-flight (DynoAIPreflight)

Use `dynoai_preflight.py` exactly like the bridge script:

1. Power Core → Tools → TuneLab → Manage Scripts → *Add*
2. Select `api/services/integrations/powercore/dynoai_preflight.py`
3. Click **Perform Correction** to run the check on the most recently loaded log

The script evaluates:

- Battery voltage (`B+`/aliases)
- AFR front and rear channels (`WBO2 F` / `WBO2 R` + aliases)
- Engine temp (`ET`/aliases)
- Intake temp (`IAT`/aliases)

Output is a single verdict dialog:

- **READY FOR PULL**
- **READY with warnings - proceed with caution**
- **NOT READY - do not pull**

## DynoAI Autotune (Preview + Apply)

`dynoai_autotune.py` now provides:

- F1 preview export (`VE_Front_Correction_2D.csv`, `VE_Rear_Correction_2D.csv`, `correction_summary.json`)
- F1.1 dual-cylinder apply (`context.PutTable`) via server-side `VEApply` + `SessionLogger`

### Install

1. Power Core → Tools → TuneLab → Manage Scripts → *Add*
2. Select `api/services/integrations/powercore/dynoai_autotune.py`
3. Ensure your DynoAI repo root and Python path in script defaults are valid:
   - `DEFAULT_REPO_ROOT`
   - `DEFAULT_PYTHON`

The script shells to:

```powershell
python -m tools.autotune.tunelab_entrypoint preview --help
python -m tools.autotune.tunelab_entrypoint apply --help
```

### Autotune Preview Usage

1. Load a log in Data Center that includes both front and rear wideband channels.
2. Run the `DynoAIAutotune` script.
3. Review the preview dialog:
   - Front (VE F) summary metrics
   - Rear (VE R) summary metrics
   - Safety-aware banner and block reasons from `summary["safety"]`
4. Click **Export Only** to copy outputs into `runs/<run_id>/corrections/`:
   - `VE_Front_Correction_2D.csv`
   - `VE_Rear_Correction_2D.csv`
   - `correction_summary.json`
   - optional `.pvv` patch when emitted by CLI flag

### F1.1 Apply Flow

When the loaded log is dual-cylinder and `summary["safety"]["apply_blocked"]` is false:

1. Click **Apply to Loaded Tune**
2. Confirm backup prompt (manual Power Core Save As recommended)
3. Script exports current loaded VE front/rear tables to temp CSV
4. Script calls:
   - `python -m tools.autotune.tunelab_entrypoint apply --run-id ... --output-dir ... --base-front ... --base-rear ...`
5. CLI runs `VEApply(max_adjust_pct=15.0)` and records events using `SessionLogger`
6. Script reads `VE_Front_Applied.csv` / `VE_Rear_Applied.csv`, writes tables via `context.PutTable(...)`
7. Artifacts land in:
   - `runs/<run_id>/session_log.json`
   - `runs/<run_id>/snapshots/`
   - `logs/autotune_applied.log`
   - `runs/<run_id>/corrections/` (export copies)

### Button State Matrix

- **Dual-cylinder + not blocked:** Apply button visible and enabled
- **Dual-cylinder + blocked:** Apply visible but disabled; reason messages shown
- **Single-cylinder mode:** Apply hidden (export-only by design)

### Table Name Overrides

Tune names vary between Power Core builds. Edit these constants in `dynoai_autotune.py` if needed:

- `VE_FRONT_TABLE_NAME`
- `VE_REAR_TABLE_NAME`

Use `inspect_tunelab_context.py` in TuneLab to probe the active API/table names before changing constants.

### Known limits

- Uses static MAP-indexed AFR target curve (`static_map_curve_v1`) in F1.
- `from_tune.AFR_Target` is reserved for F1.1 and not enabled in this release.
- Temp working files are cleaned up after the run; only exported files are persisted.

### Single-wideband logs

- If the loaded log only has one wideband channel populated (front or rear),
  the TuneLab script auto-enables **single-cylinder mode** and passes
  `--single-cylinder front` or `--single-cylinder rear` to the CLI.
- Preview dialog shows the populated cylinder's metrics and marks the other
  side as "Not computed." with an orange banner making the mode explicit.
- The summary JSON carries `"mode": "single_cylinder_front" | "single_cylinder_rear"`
  and the missing side as `null`. No CSV is emitted for the missing side.
- Apply is safety-blocked in single mode via `BlockReason.type == "partial_cylinder"`.

## Watch-folder auto-import (F4)

F4 adds a backend watcher service (not a TuneLab script) that monitors common
Power Core folders and streams ingest events over SSE.

### Enable and configure

1. Install both dependency sets so `watchdog` is present regardless of your
   startup flow:

   ```powershell
   pip install -r requirements.txt
   pip install -r api\requirements.txt
   ```

2. (Optional) Add machine-specific folders:
   - Copy `config/watch_folder.example.yaml` to `config/watch_folder.yaml`
   - Add extra folders under `folders:`
3. Start the API in single-process mode (F4 scope):
   - Local dev is supported
   - Multi-worker deployment is intentionally out of scope for this phase

### API endpoints

- `GET /api/powercore/watch/status` - service status, configured folders,
  subscriber count, and recent event counters
- `GET /api/powercore/watch/recent?limit=20` - recent watch events
- `GET /api/powercore/watch/stream` - SSE stream (`text/event-stream`)
- `POST /api/powercore/watch/rescan` - bounded rescan for one configured folder

Example rescan body:

```json
{
  "folder": "C:\\Users\\dawso\\OneDrive\\Documents\\PowerCoreBackups",
  "limit": 25
}
```

### Logs

- Structured watch events are written to `logs/watch_folder.log`
- OneDrive cloud-only placeholders are skipped and logged as such

## Known Limitations

- **HP and TQ values are manual.** Power Core ECU logs don't contain
  dyno-side channels like horsepower or torque — those come from the dyno
  itself. The bridge auto-detects peak RPM and pre-fills the
  `HP Peak RPM` / `TQ Peak RPM` fields, but you must enter peak HP and peak
  TQ values manually (read them off your dyno chart).
- **"Open Folder" requires Explorer.** The success dialog's Open Folder
  button shells out to `explorer.exe`; on non-Windows installations
  (unlikely for Power Core anyway) it will silently no-op.
- **Multiple loaded files:** if Data Center has several runs loaded, the
  bridge auto-detects peaks from the **most recently loaded** file only. If
  you want a different source, close and reload the file you want.

## Notes

- All errors from the DynoAI CLI are surfaced in a WinForms MessageBox
  (with stdout + stderr).
- Validation errors (missing Run ID, non-numeric HP, etc.) show a
  MessageBox and keep the form open so you can fix the offending field.
- Feel free to customize the dialog (extra fields, presets, etc.) — the
  script is plain IronPython 2.7 and reloads every time Power Core starts.
