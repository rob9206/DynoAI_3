"""Session-level services for DynoAI workspace.

This package houses the v3 session schema (`session_v3.py`) and the
session-execution coordinators (phased pull controller, dispatch readiness
evaluator, P0 plausibility checker) that consume it.

The v3 schema is layered on top of the existing `TuningSession` dataclass in
`api/services/tuning_workspace.py`; legacy v0 sessions remain readable.
"""
