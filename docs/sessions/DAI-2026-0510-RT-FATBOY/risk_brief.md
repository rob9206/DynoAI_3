# Risk Brief

*   **Risk:** Injector Duty Cycle High
    *   **Severity:** CRITICAL
    *   **Trigger:** Injector duty cycle exceeds 85% (`INJECTOR_DUTY_HALT_PCT`).
    *   **Mitigation:** `api/services/jetdrive/jetdrive_realtime_analysis.py` (`_detect_alerts`) emits a `CRITICAL` alert of type `INJECTOR_DUTY_HIGH`, prompting an immediate halt.

*   **Risk:** Lean Condition / Implausible AFR
    *   **Severity:** CRITICAL
    *   **Trigger:** AFR drops below 10.0 (`AFR_MIN_PLAUSIBLE`) or exceeds 18.0 (`AFR_MAX_PLAUSIBLE`), or a lean streak exceeds the configured maximum consecutive cells.
    *   **Mitigation:** `dynoai/core/kernel_sentinel.py` (`evaluate_lean_streak_from_grid`) and `api/services/jetdrive/jetdrive_realtime_analysis.py` (`_detect_alerts`) emit `CRITICAL` alerts, triggering `halt_on_breach`.

*   **Risk:** Thermal Overload (EGT / Oil Temp)
    *   **Severity:** CRITICAL
    *   **Trigger:** EGT exceeds `egt_redline_f` or Oil Temp exceeds `oil_temp_rollback_f`.
    *   **Mitigation:** `dynoai/core/kernel_sentinel.py` (`evaluate_realtime_sample`) emits a `CRITICAL` alert, triggering `halt_on_breach`.

*   **Risk:** Excessive VE Correction
    *   **Severity:** MEDIUM
    *   **Trigger:** The calculated VE correction exceeds safe bounds.
    *   **Mitigation:** `api/services/autotune_workflow.py` (`calculate_corrections`) clamps the calculated correction to `MAX_CORRECTION_PCT` (10.0%), and `dynoai/core/ve_operations.py` (`VEApply.apply`) enforces a hard floor of `DEFAULT_MAX_ADJUST_PCT` (7.0%). The `kernel_sentinel` can further tighten this limit.