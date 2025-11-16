# Core Engine [MATH-CRITICAL]

This directory contains the core DynoAI tuning engine.

## Expected Files

### Main Engine
- `ai_tuner_toolkit_dyno_v1_2.py` - Main CLI engine for dyno analysis
- `ve_operations.py` - VE table apply/rollback with SHA-256 verification
- `io_contracts.py` - Path safety and file fingerprinting

### Utilities Package
- `dynoai/` - Shared utilities
  - `api/xai_blueprint.py` - Flask blueprint for xAI Grok chat
  - `clients/xai_client.py` - xAI API client wrapper
  - `constants.py` - Shared constants

## Safety Notice

All files in this directory are **MATH-CRITICAL**. Changes require:
- Design document
- Validation plan with before/after comparisons
- Maintainer approval
- Extended review period (3-7 days minimum)

See `docs/DYNOAI_SAFETY_RULES.md` for complete safety policies.
