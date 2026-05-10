# Shop Runbook: DAI-2026-0510-RT-FATBOY

## 1. Preflight Checklist
*   [ ] Verify bike condition (tires, belt/chain, no leaks).
*   [ ] Check fluid levels (oil, primary, transmission).
*   [ ] Confirm fuel grade matches customer intake.
*   [ ] Warm up AFR sensors before starting the engine.
*   [ ] **PV3 Troubleshooting Note:** The Power Vision `offset_extra_seed == VIN_LOCK_EXTRA_SEED_OFFSET_v0101` assertion spam in `AssertLog.txt` is a known firmware bug on version `2.9.2-1715`. **Ignore this spam. Do not attempt to unlock or bypass.**

## 2. P0 Plausibility Run
Before proceeding with tuning, validate the engine's baseline performance against known 103ci parameters.
*   Perform a baseline pull to gather peak torque and BMEP/BSFC data.
*   **Action:** POST to the plausibility endpoint:
    ```bash
    POST /api/workspace/vehicles/<vid>/sessions/<sid>/p0_plausibility
    {
        "peak_tq_ftlb": <measured_value>,
        "peak_tq_rpm": <measured_value>,
        "bmep_psi": <measured_value>,
        "bsfc_lb_hp_hr": <measured_value>
    }
    ```
*   Ensure the response indicates `p0_plausibility_ok: true` before advancing to P1.

## 3. Phased Pulls (P0..P4)
Execute the tuning phases sequentially. Monitor the realtime analysis engine for alerts.
*   **P0:** Baseline validation (completed above).
*   **P1:** VE sweep (steady-state mapping).
*   **P2:** AFR refinement.
*   **P3:** Timing optimization.
*   **P4:** Final validation pull.
*   **Stop-on-Breach:** If any `CRITICAL` alert is emitted during a pull, abort the pull immediately and return to idle.

## 4. Halt + Rollback Procedure
If the realtime engine emits a `kernel_sentinel` or `injector_duty_high` critical alert:
1.  **Halt:** Immediately close the throttle, clutch in, and hit the kill switch if necessary.
2.  **Assess:** Review the alert details in the UI to determine the cause (e.g., lean streak, thermal overload, injector maxed out).
3.  **Rollback:** If the current iteration is deemed unsafe, roll back the VE corrections using the CLI tool:
    ```bash
    python -m dynoai.core.ve_operations rollback \
        --current <path_to_current_ve.csv> \
        --metadata <path_to_apply_meta.json> \
        --output <path_to_restored_ve.csv>
    ```
4.  Flash the restored VE table back to the ECU before resuming.

## 5. Dual-Bank Verification
Before relying on the `use_dual_bank_weighting` feature (which applies a +15% bias to the rear cylinder):
1.  Verify that the physical wideband sensors are correctly mapped to the data channels (e.g., Front = AFR1, Rear = AFR2).
2.  Confirm sensor placement matches the configuration.
3.  If sensors are swapped or single-channel, disable dual-bank weighting to prevent erroneous corrections.