# Inferred Defaults Brief

*   **Field:** `build_spec.displacement_ci`
    *   **Value:** 103.0
    *   **Source:** User statement ("fat boy cvo is 103 stock")
    *   **Confidence:** High
    *   **Kill-Switch:** Verify stock 103ci cylinders/heads are present before dispatch.
    *   **Note:** The `.pvv` export showed `tbl_engine_displacement = 94.6 CID`. This is a Power Vision export artifact and should be ignored; the actual displacement is 103ci.

*   **Field:** `vehicle.vin`
    *   **Value:** 1HD1PNF156Y953325
    *   **Source:** `DiagnosticsHistory.txt`
    *   **Confidence:** High
    *   **Kill-Switch:** Verify VIN on the frame matches before flashing.

*   **Field:** `build_spec.ecm.part_number`
    *   **Value:** 32498-05A
    *   **Source:** `DiagnosticsHistory.txt` and `.pvv` export
    *   **Confidence:** High
    *   **Kill-Switch:** Verify ECM part number label matches.

*   **Field:** `build_spec.ecm.current_calibration_source`
    *   **Value:** 141NY103-001
    *   **Source:** `DiagnosticsHistory.txt` and `.pvv` export
    *   **Confidence:** High
    *   **Kill-Switch:** Verify current calibration ID via Power Vision before overwriting.

*   **Field:** `build_spec.injectors.flow_rate_g_s`
    *   **Value:** 31.07 lb/hr (approx 3.91 g/s)
    *   **Source:** `.pvv` export (`tbl_injector_size`)
    *   **Confidence:** High
    *   **Kill-Switch:** Verify injector part numbers match stock 31.07 lb/hr units.

*   **Field:** `hardware.ecm_interface.firmware_version`
    *   **Value:** 2.9.2-1715
    *   **Source:** `DiagnosticsHistory.txt`
    *   **Confidence:** High
    *   **Kill-Switch:** Ensure Power Vision is running this firmware version.
    *   **Note:** The Power Vision `offset_extra_seed == VIN_LOCK_EXTRA_SEED_OFFSET_v0101` assertion spam in `AssertLog.txt` is a known firmware bug on `2.9.2-1715`, NOT a security event.