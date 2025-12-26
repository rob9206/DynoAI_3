Cleanup summary (Dec 15, 2025)
--------------------------------
- Removed legacy nested copies of the repo to keep a single canonical source tree.
- Dropped vendored/ephemeral artifacts from version control (.coverage, backend_error.log, backend_output.log) and cleared local node_modules/.venv caches.
- Hardened ignore rules in .gitignore and .dockerignore to keep build outputs, caches, logs, and future nested copies out of the repo.
- Updated pytest config to avoid descending into any future DynoAI_* duplicates during discovery.

Notes
- Tests and frontend build were not run as part of this cleanup; please run them after reinstalling dependencies as needed.

