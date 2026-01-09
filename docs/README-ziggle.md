# DynoAI Documentation Index

This directory consolidates key project documents. Use this as a map rather than duplicating content.

## Core Guides
- `../README.md` – High-level project overview.
- `../README_VE_OPERATIONS.md` – Safety-critical VE apply/rollback system.
- `Dyno_AI_Tuner_v1_2_README.txt` – Detailed CLI toolkit usage (original text form).
- `FXDLS_Wheelie_VE_Logging_README.txt` – Real-world logging reference.
- `../QUICK_START_WEB.md` – Web integration quick start.

## Development & Process
- `../CONTRIBUTING.md` – How to set up env, run self-test, and contribute.
- `../CODE_OF_CONDUCT.md` – Community standards.
- `../CHANGELOG.md` – Version history.
- `../IMPLEMENTATION_SUMMARY.md` – Architectural implementation notes.
- `../FINAL_SUMMARY.md` – Release or milestone summary.

## Safety & Operations
- `../README_VE_OPERATIONS.md` – VE operations safety principles (never edit tables directly).
- `../EXCEPTION_HANDLER_VALIDATION.md` – Error handling strategies.
- `../RUNTIME_ERROR_FIX.md` – Common runtime error resolutions.
- `../TWO_STAGE_KERNEL_INTEGRATION.md` – Kernel smoothing evolution.

## Integration & Web
- `../WEB_INTEGRATION_SUMMARY.md` – Browser/dashboard integration notes.
- `../INTEGRATION_GUIDE.md` – Multi-component integration strategy.

## Testing & Quality
- `../QA_RELEASE_REPORT.md` – QA outcomes.
- `../CODE_IMPROVEMENTS_2025-11-08.md` – Suggested refactors/enhancements.

## Data & Formats
- `../CSV_FILE_TYPES.md` – Input/output CSV schema catalog.
- `Dawson_Dynamics_Harley_ECM_Reference_Sheet.pdf` – ECM reference.
- `dynojet_target_tune_for_harley_softail_dyna20122016.pdf` – External tuning reference.

## Legacy Bundles
- `legacy/README_DROPIN.txt` – Drop-in checklist for the Reliability Pack bundle.
- `legacy/README_MasterBuild.txt` – Notes that accompanied the v1.2.1 master build drop.
- `legacy/README_SETUP.txt` – Windows quick-setup directions for the original bundle.

## Next Steps
To reduce clutter:
1. Confirm if any remaining top-level README variants should move into `docs/legacy/` or be retired entirely.
2. Migrate core Python modules into `src/dynoai/` (planned).
3. Auto-generate dashboard docs excerpt once HTML spec stabilizes.

If adding new docs, link them here rather than creating isolated files.
