# DynoAI_3

Intelligent dyno tuning system for Harley-Davidson ECM calibration.

## Repository Layout (v3)

This repository is structured for clarity and maintainability:

- **`core/`** - Core tuning engine modules
  - Main tuner script: `ai_tuner_toolkit_dyno_v1_2.py`
  - VE table operations: `ve_operations.py` (VEApply, VERollback)
  - I/O contracts: Path safety and file fingerprinting
  - Kernel implementations: k1, k2, k3 smoothing algorithms

- **`io/`** - I/O contracts and manifests
  - File I/O safety contracts (`io_contracts.py`)
  - Manifest schemas and validation
  - CSV parsing utilities

- **`tool/`** - CLI tools and data generators
  - `ai_tuner_toolkit_dyno_v1_2.py` - Main tuner CLI entrypoint
  - `selftest_runner.py` - Self-test suite runner
  - `generate_dense_dyno_data.py` - Dense test data generator
  - `generate_large_log.py` - Large log file generator
  - `debug_afr_error.py` - AFR error debugging tool
  - `make_ve_3d.py` - 3D VE table visualizer

- **`scripts/`** - CI/CD and development helpers
  - `build_project_tree.py` - Repository structure visualization
  - Local development scripts
  - Build automation

- **`experiments/`** - Research and prototypes
  - Gradient analyzers
  - Visualization experiments
  - New algorithm prototypes (not production)

- **`tests/`** - Main test suite
  - Unit tests: `test_k1.py`, `test_k2.py`, `test_k2_fixed.py`, `test_k3.py`
  - Integration tests: `selftest.py`
  - VE operation tests
  - Run via `pytest` or `tool/selftest_runner.py`

**Run directories** (generated at runtime):
- `runs/{run_id}/` - Dyno tuning run outputs
- `ve_runs/{run_id}/` - VE apply/rollback outputs
- `ve_runs/preview/` - VE preview operations

## Documentation

- **[Agent Prompts](docs/DYNOAI_AGENT_PROMPTS.md)** - Three specialized coding agent prompts for safe DynoAI development
- **[Architecture Overview](docs/DYNOAI_ARCHITECTURE_OVERVIEW.md)** - System architecture and component interactions
- **[Safety Rules](docs/DYNOAI_SAFETY_RULES.md)** - Critical safety policies and invariants

## Quick Start: Using DynoAI Agents

This repository includes three specialized agent prompts that can be used with Cursor, ChatGPT, or GitHub Copilot:

### 1. Reorg & Infra Agent
**Purpose:** Repository organization, CI/CD, documentation  
**File:** [`docs/prompts/agent1_reorg_infra.md`](docs/prompts/agent1_reorg_infra.md)  
**Never touches:** Tuning math, kernels, VE/AFR behavior

### 2. Bug Fixer Agent
**Purpose:** Fix failing tests, bugs, robustness issues  
**File:** [`docs/prompts/agent2_bug_fixer.md`](docs/prompts/agent2_bug_fixer.md)  
**Never touches:** Tuning algorithms, kernel behavior

### 3. Kernel & Math Guardian Agent
**Purpose:** Review PRs for safety violations  
**File:** [`docs/prompts/agent3_math_guardian.md`](docs/prompts/agent3_math_guardian.md)  
**Role:** Reviewer only - does not make edits

**See [Agent Prompts Documentation](docs/DYNOAI_AGENT_PROMPTS.md) for complete usage instructions.**