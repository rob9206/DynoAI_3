# MasterTune Automation

This project supports a COM-first automation flow with UI fallback hooks for
bulk MasterTune ingestion.

## 1) Probe COM interfaces

```powershell
python "c:\Dev\DynoAI_3\scripts\probe_tts_com.py" --try-dispatch
```

Use `--json` for machine-readable output.

## 2) Run automation orchestrator

```powershell
python "c:\Dev\DynoAI_3\scripts\auto_mastertune_ingest.py" --calibration-dir "C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations" --library-dir "c:\Dev\DynoAI_3\data\calibration_library" --max-files 20 --skip-existing
```

This script:

1. scans MT files
2. ensures TSV templates exist
3. tries COM extraction (adapter placeholder currently)
4. optionally executes UI export hook command
5. ingests filled TSV sets via `ingest_mastertune_tsv.py`
6. writes a JSON report

## 3) Optional UI export hook

Pass a command template that receives these placeholders:

- `{mt_file}`
- `{out_dir}`
- `{ve_front}`
- `{ve_rear}`
- `{lambda_tsv}`
- `{axis_mode}`

Example:

```powershell
python "c:\Dev\DynoAI_3\scripts\auto_mastertune_ingest.py" --calibration-dir "C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations" --library-dir "c:\Dev\DynoAI_3\data\calibration_library" --max-files 20 --report-json "C:\Users\dawso\AppData\Local\Temp\auto_ingest_report.json" --axis-mode map --ui-export-cmd-template "powershell -ExecutionPolicy Bypass -File c:\Dev\DynoAI_3\scripts\export_mt_tables.ps1 -MtFile {mt_file} -OutDir {out_dir} -VeFront {ve_front} -VeRear {ve_rear} -LambdaTsv {lambda_tsv} -AxisMode {axis_mode}"
```

Targeted one-file run by filename token:

```powershell
python "c:\Dev\DynoAI_3\scripts\auto_mastertune_ingest.py" --calibration-dir "C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations\BigTwin" --file-contains "EAS600" --axis-mode map --max-files 1 --library-dir "c:\Dev\DynoAI_3\data\calibration_library" --ui-export-cmd-template "powershell -ExecutionPolicy Bypass -File c:\Dev\DynoAI_3\scripts\export_mt_tables.ps1 -MtFile {mt_file} -OutDir {out_dir} -VeFront {ve_front} -VeRear {ve_rear} -LambdaTsv {lambda_tsv} -AxisMode {axis_mode}"
```

After hook execution, TSV files are checked and ingested if filled.

## 4) Templates-only mode (non-interactive safe)

Generate TSV templates for all files without attempting UI export or ingest.
Safe to run from Dispatch, CI, or any non-interactive runner:

```powershell
python "c:\Dev\DynoAI_3\scripts\auto_mastertune_ingest.py" --calibration-dir "C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations\BigTwin" --templates-only --max-files 20
```

This creates the empty TSV scaffolds (`ve_front_map.tsv`, `ve_rear_map.tsv`,
`lambda_map.tsv`) under each file's `tsv_templates/` directory, then stops.
No `input()` prompts, no pywinauto, no MasterTune interaction.

## 5) Fully automated dispatcher (unattended)

Uses `pywinauto` to open each MT file, navigate to tables, and copy grids
automatically. No manual input required. Saves progress to a queue JSON so
interrupted runs can be resumed.

First run (builds queue and starts processing):

```powershell
python "c:\Dev\DynoAI_3\scripts\dispatch_mastertune.py" --calibration-dir "C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations\BigTwin" --library-dir "c:\Dev\DynoAI_3\data\calibration_library" --axis-mode map --max-files 20
```

Resume after interruption:

```powershell
python "c:\Dev\DynoAI_3\scripts\dispatch_mastertune.py" --resume
```

Options:

- `--max-retries 3` — attempts per file before marking failed (default 3)
- `--inter-file-delay 2.0` — seconds between files (default 2)
- `--file-contains "EAS"` — only process matching filenames (repeatable)
- `--queue-path <path>` — custom queue JSON location

Queue file: `data/mastertune_catalog/dispatch_queue.json`

## 6) Corpus contract and clean-run criteria

MasterTune corpus entries are expected to carry a stable contract before they
are considered ready for downstream v3 seeding:

- engine-family hardware metadata
- front VE grid and optional rear VE grid
- AFR targets derived from lambda
- RPM/MAP bins and shape metadata
- provenance metadata (`source_name`, `source_path`, operator, queue metadata)
- deterministic `source_identity` for idempotent re-ingest

Use the audit/requeue tools as the quality gate:

```powershell
python "c:\Dev\DynoAI_3\scripts\audit_dispatch_outputs.py" --queue-path "c:\Dev\DynoAI_3\data\mastertune_catalog\dispatch_queue.json" --report-json "c:\Dev\DynoAI_3\output\audit_report.json"
python "c:\Dev\DynoAI_3\scripts\requeue_suspect_items.py" --queue-path "c:\Dev\DynoAI_3\data\mastertune_catalog\dispatch_queue.json" --report-json "c:\Dev\DynoAI_3\output\audit_report.json" --dry-run
```

After fixes/re-capture, build a catalog summary:

```powershell
python "c:\Dev\DynoAI_3\scripts\index_mastertune_calibrations.py" --calibration-dir "C:\Users\dawso\OneDrive\Documents\TTS\HD\Calibrations\BigTwin" --library-dir "c:\Dev\DynoAI_3\data\calibration_library"
```

Recommended clean-corpus acceptance criteria:

- `parse_failures == 0` for target batch
- duplicate source identities are not growing across re-runs
- missing rear VE is explainable for known single-cylinder/single-table sources
- missing AFR targets and bad-shape records are zero (or explicitly waived)

## 7) Notes

- MT payloads are encrypted; direct binary table parsing is not used.
- Current COM step is a scaffold until a concrete TTS automation interface is wired.
- The JSON report (orchestrator) defaults to:
  `c:\Dev\DynoAI_3\data\mastertune_catalog\auto_ingest_report.json`
- The dispatch queue defaults to:
  `c:\Dev\DynoAI_3\data\mastertune_catalog\dispatch_queue.json`
