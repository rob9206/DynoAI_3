# Migration Plan: src/ layout and test organization

This document outlines a safe, incremental path to a cleaner layout without breaking existing workflows.

## Goals
- Introduce `src/dynoai/` package for core Python modules.
- Centralize tests under `tests/` while maintaining current test discoverability.
- Preserve CLI entry points and GUI behavior.

## Phase 1: Prepare (No Moves)
- Keep current files in place.
- Add `src/dynoai/` with `__init__.py` (empty) as a staging area.
- Ensure `tests/` holds new tests; legacy tests at root continue to run.

## Phase 2: Duplicate Modules (Opt-In)
- Copy (not move) `ai_tuner_toolkit_dyno_v1_2.py`, `ve_operations.py`, and `io_contracts.py` into `src/dynoai/`.
- Provide thin wrappers at root that import from `dynoai` and call `main()` to keep CLI usage stable.
- Run `selftest_runner.py` and unit tests to validate behavior.

## Phase 3: Switch Imports
- Update internal imports to reference `dynoai.*` where applicable.
- Run tests and accept PR once green.

## Phase 4: Remove Duplicates
- After a release cycle with both paths supported, remove root copies, leaving only wrappers or console scripts.

## Test Organization
- New tests go in `tests/`.
- Gradually move legacy `test_*.py` from root into `tests/` as imports are stabilized.

## Tooling
- Add optional dev env var: `PYTHONPATH=src` during local runs.
- Consider packaging with `pyproject.toml` in a future pass.

## Rollback
- If issues arise, revert to root modules immediately (no destructive moves until Phase 4).
