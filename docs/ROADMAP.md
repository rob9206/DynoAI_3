# DynoAI Practical Roadmap (2025–2028)

This roadmap focuses on high-impact, practical features that can be built on top of the immutable DynoAI math core. Items are grouped by horizon, but can be pulled forward if resources allow.

## 0–6 Months: "Make Today's Dyno Sessions Magical"

1. VE Table Time Machine (Session Replay v1)

- Record every VEApply/VERollback operation, AFR map, and key decision per dyno session.
- Allow replay of a session step-by-step with a timeline:
- See VE table, AFR, and torque curves at any point in time.
- Show "what changed" between steps.
- Store metadata in runs/{run_id}/session_log.json (or similar) with deterministic format.
- No new math: this is orchestration, logging, and visualization of existing outputs.

2. Multi-Fuel Personality System (Profiles v1)

- Allow multiple VE "personalities" per vehicle: e.g., 93, E85, 100 octane.
- Store a named profile set per vehicle, sharing the same core math:
- Each profile = VE table + spark suggestions + AFR targets.
- Provide:
- Manual profile switcher in CLI/GUI.
- A diff view between profiles (cells that change between fuels).
- No auto-conversion yet—just clean storage, switching, and comparison.

3. Thermal & Atmospheric Compensation Overlays v1

- Add a lightweight compensation layer that:
- Reads intake/coolant/oil temps from logs when available.
- Reads barometric pressure / approximate density altitude (manual input or simple API call).
- Output:
- Recommended correction overlays (not modified VE math):
- "Thermal overlay": small % fuel / timing adjustments vs. temperature.
- "Atmospheric overlay": suggested changes vs. density altitude.
- Keep this as advisory overlays that tuners can choose to apply via VEApply.

4. Transient Response Analyzer v1

- Analyze logs for throttle tip-in/tip-out vs. AFR response.
- Report:
- Where transient AFR deviates from target.
- Simple, human-readable suggestions:
- "Under-fueling during tip-in between 2500–3500 RPM, medium load."
- Output a transient "heatmap" (e.g., CSV + simple HTML) without changing VE tables.
- Leave actual AE/DE table edits to the tuner or to the ECU software; DynoAI focuses on diagnostics and suggestions.

5. Tune Stability & Confidence Score v1 (Entropy-Light)

- Compute a simple "stability score" for a session:
- Based on how much VE changes across pulls at the same RPM/load points.
- Lower change = higher stability/confidence.
- Show this as:
- Single numeric score per session.
- List of cells/regions still "moving around" too much between pulls.
- No advanced ML required: just statistics over existing VE deltas and AFR errors.

## 6–18 Months: "Predictive & Multi-Scenario Tuning"

6. One-Pull Baseline™ v1

- From one conservative partial-throttle pull:
- Use existing AFR error and VE delta calculations to extrapolate a safe full-load starting VE surface.
- Constraints:
- Emphasize safety: bias rich and conservative timing in extrapolated zones.
- Emit a "baseline candidate" VE table plus a confidence map (where the prediction is strong vs. weak).
- This is built entirely on top of the current VEApply/AFR binning math.

7. Predictive Knock / Mechanical Risk Hints v1

- Use existing torque curves, AFR, and variance over pulls to:
- Flag patterns that often correlate with knock or mechanical issues.
- Example outputs:
- "Unusual torque drop around 4800 RPM—possible knock or airflow restriction."
- "One cylinder requires significantly more fuel than others—possible injector issue."
- Keep it strictly advisory:
- No automatic changes to VE math.
- Tuners remain in full control.

8. Instant Fuel Switch Helper v1

- Given:
- A tuned VE table for Fuel A.
- Known stoich for Fuel B (e.g., 93 → E85).
- Generate:
- A suggested VE overlay to move from A to B (rich-biased, safe).
- Mark all cells derived from this process as "needs verification pulls."
- Still require tuner validation; DynoAI simply automates the first draft.

## 18–36 Months: "Global Intelligence & Virtual Scenarios"

9. Neural Tune Prediction Network v1

- Train a model on anonymized historical VE tables, AFR responses, and convergence behavior.
- Provide:
- Starting VE suggestions for a new engine/mod combo before the first pull.
- Fully wrap around the sealed math:
- Model only suggests inputs; VEApply/VERollback remain canonical.

10. Virtual Scenario Branching ("What-If" Paths v1)

- Allow multiple "branches" of a tune to be simulated using prior session data:
- Branch A: more timing in mid-range.
- Branch B: richer under boost.
- Use existing historical logs + models to estimate outcomes before real pulls.
- Tuners choose which branch to validate on the dyno.

## Principles

- The core math (VEApply, VERollback, AFR binning, torque weighting, k1/k2/k3) remains sealed and immutable.
- New capabilities are delivered as:
- Logging + replay layers.
- Overlays and suggestions.
- Diagnostic and predictive analytics.
- All new features must be:
- Deterministic.
- Test-covered.
- Reversible by design (no one-way operations without rollback).
