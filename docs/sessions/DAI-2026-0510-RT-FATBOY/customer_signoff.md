# Customer Sign-Off and Safety Limits

By signing below, you acknowledge and agree to the safety limits and tuning parameters established for your vehicle during this session.

**Safety Limits in Effect:**
*   **WOT Lambda Target:** `0.88` (Target Air/Fuel Ratio at Wide Open Throttle)
*   **EGT Redline:** Enforced via `kernel_sentinel` (Engine will be halted if Exhaust Gas Temperature exceeds redline)
*   **EGT Warning:** Enforced via `kernel_sentinel` (Operator alerted if EGT reaches warning threshold)
*   **Oil Temperature Rollback:** Enforced via `kernel_sentinel` (Timing/fueling adjustments applied if oil temperature exceeds safe limits)
*   **Workflow Correction Ceiling:** `±10.0%` (Maximum VE adjustment calculated per iteration, per `AutoTuneWorkflow.MAX_CORRECTION_PCT`)
*   **Apply Correction Ceiling:** `±7.0%` (Absolute maximum VE adjustment applied to the ECU, per `DEFAULT_MAX_ADJUST_PCT`)

These limits are hard-coded into our tuning engine to protect your motorcycle from thermal and mechanical stress.

**Customer Signature:** ___________________________  **Date:** ____________