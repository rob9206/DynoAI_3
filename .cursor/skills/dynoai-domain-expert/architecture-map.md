# DynoAI Architecture Map

## Backend Route Structure

All routes are Flask Blueprints registered in `api/app.py` with graceful degradation (try/except).

| Prefix | Blueprint | File | Purpose |
|---|---|---|---|
| `/api/health` | `health_bp` | `api/health.py` | Liveness/readiness probes |
| `/api/jetstream` | `jetstream_bp` | `api/routes/jetstream.py` | Dynojet data polling |
| `/api/timeline` | `timeline_bp` | `api/routes/timeline.py` | VE Table Time Machine |
| `/api/wizards` | `wizards_bp` | `api/routes/wizards.py` | Tuning wizards |
| `/api/jetdrive` | `jetdrive_bp` | `api/routes/jetdrive.py` | JetDrive auto-tune |
| `/api/transient` | `transient_bp` | `api/routes/transient.py` | Transient fuel comp |
| `/api/virtual-tune` | `virtual_tune_bp` | `api/routes/virtual_tune.py` | Closed-loop tuning |
| `/api/training` | `training_bp` | `api/routes/training.py` | Operator training sim |
| `/api/powercore` | `powercore_bp` | `api/routes/powercore.py` | Power Core integration |
| `/api/reports` | `reports_bp` | `api/routes/reports.py` | PDF report generation |
| `/api/ea` | `ea_bp` | `api/routes/engine_analyzer.py` | Engine Analyzer |
| `/api/nextgen` | `nextgen_bp` | `api/routes/nextgen.py` | NextGen analysis |
| `/api/reliability` | `reliability_bp` | `api/reliability_integration.py` | Circuit breakers |

Core endpoints in `api/app.py` directly:
- `POST /api/analyze` -- Upload and analyze CSV (async)
- `GET /api/status/<run_id>` -- Analysis status
- `GET /api/download/<run_id>/<filename>` -- Download output
- `GET /api/ve-data/<run_id>` -- VE table data
- `POST /api/apply` -- Apply VE corrections (protected)
- `POST /api/rollback` -- Rollback corrections (protected)

## Frontend Route Map

All routes in `frontend/src/App.tsx`, code-split via `React.lazy()`:

| Path | Component | Feature |
|---|---|---|
| `/jetdrive` | `JetDriveAutoTunePage` | Main tuning interface |
| `/jetstream` | `JetstreamPage` | Dynojet integration |
| `/runs/:runId` | `RunDetailPage` | Run details |
| `/dashboard` | `Dashboard` | Overview |
| `/results/:runId` | `Results` | Analysis results |
| `/time-machine/:runId` | `TimeMachinePage` | VE Table history |
| `/history` | `History` | Run history |
| `/wizards` | `TuningWizardsPage` | Tuning wizards |
| `/training` | `OperatorTrainingPage` | Training simulator |
| `/engine-analyzer` | `EngineAnalyzerPage` | Engine analysis |

## Frontend Component Organization

```
frontend/src/
├── api/          -- API client functions (one file per domain)
├── components/
│   ├── actions/      -- Apply/Rollback controls
│   ├── autotune/     -- 3D VE surface viz
│   ├── common/       -- Layout, Loading, Logo
│   ├── engine-analyzer/  -- Build editor, prediction
│   ├── jetdrive/     -- Live tuning (30+ components)
│   ├── jetstream/    -- Jetstream integration
│   ├── livelink/     -- Gauges and charts
│   ├── reports/      -- Report generation
│   ├── results/      -- VE heatmaps, diagnostics
│   ├── session-replay/   -- Decision replay
│   ├── timeline/     -- Time Machine
│   └── ui/           -- shadcn/ui primitives (50+)
├── hooks/        -- 18 custom hooks (useTimeline, useJetDriveLive, etc.)
├── lib/          -- Axios instance, types, utilities
├── pages/        -- 11 page components
├── types/        -- bikeConfig.ts, veApplyTypes.ts
└── utils/        -- veApply/, pvvParser, performance
```

## Backend Service Layer

```
api/services/
├── autotune_workflow.py    -- Main analysis engine
├── nextgen_workflow.py     -- Physics-informed ECU reasoning
├── jetdrive/               -- JetDrive hardware (7 files)
├── engine_analyzer/        -- VE/power prediction (5 files)
├── simulation/             -- Virtual ECU + dyno sim (5 files)
├── parsers/                -- CSV/PTI/WP8 parsers (5 files)
└── ingestion/              -- External data ingestion (6 files)
```

## Database Models

| Model | Table | Key Fields |
|---|---|---|
| `Run` | `runs` | id, status, source, results_summary, peak_hp, ve_corrections_count |
| `RunFile` | `run_files` | run_id (FK), filename, file_type, storage_path |
| `ExternalDynoChart` | `external_dyno_charts` | source, engine_family, max_power_hp |
| `SyntheticWinpepRun` | `synthetic_winpep_runs` | chart_id (FK), run_path, max_hp |

## Configuration

Centralized in `api/config.py` using dataclasses:
- `AppConfig` (top-level container)
  - `ServerConfig` -- host, port, debug
  - `StorageConfig` -- upload/output/runs folders
  - `JetstreamConfig` -- API URL, key, poll interval
  - `DynoConfig` -- hardware specs (drum mass, circumference)
  - `AnalysisConfig` -- default analysis parameters
  - `RateLimitConfig` -- rate limiting settings
  - `XAIConfig` -- xAI/Grok API settings

All configurable via environment variables. See `.env.example`.
