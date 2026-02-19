# DynoAI Shop Workflow Integration

**How DynoAI Fits Into Real Dyno Shop Operations**

This document explains how DynoAI integrates with actual shop workflows, including the differences between dyno types and how NextGen features enhance the tuning process.

---

## 1. Current Architecture: DynoAI is Post-Processing

DynoAI doesn't control the dyno. It's an analysis engine that consumes CSV logs and produces correction tables. The physical workflow today is:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Dyno      │    │  Logging    │    │   DynoAI    │    │  Flash to   │
│   Pull      │───▶│  Software   │───▶│  Analysis   │───▶│    ECU      │
│             │    │ (WinPV/DJ)  │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     ▲                                       │
     └───────────────────────────────────────┘
              Iterate until converged
```

The operator runs the dyno, the logging software captures data, DynoAI analyzes offline, and corrections get flashed back. Repeat.

---

## 2. Inertia vs. Eddy Current: Why It Matters

### Inertia Dyno (Dynojet, most common)

- Measures power from drum acceleration during WOT sweeps
- You get data along a **diagonal slice** through the RPM/MAP space (RPM rising, MAP at WOT)
- Good for peak power tuning, but you're only hitting high-MAP cells
- Low/mid MAP cells (cruise, part throttle) require street logging or load-box tricks

### Eddy Current / Load-Holding Dyno (Mustang, Dynapack, Superflow)

- Can hold specific RPM while you vary throttle (and thus MAP)
- Lets you systematically fill every cell in the grid
- Hold 3000 RPM, sweep throttle from closed to WOT = **vertical slice** through table
- Hold 50% throttle, sweep RPM = **horizontal slice**
- Much better for steady-state VE correction because you can dwell in each cell

### What DynoAI Cares About

DynoAI doesn't know or care what type of dyno you have. It just sees the logged data. But the *quality* of data differs dramatically:

| Dyno Type | Steady-State Coverage | Transient Data | WOT Coverage |
|-----------|----------------------|----------------|--------------|
| Inertia | Poor (street logging needed) | Good (accel pulls) | Excellent |
| Eddy Current | Excellent (can dwell) | Moderate | Excellent |

---

## 3. How NextGen Changes the Workflow

The NextGen additions (mode detection, cause trees, next-test planning) create a feedback loop that tells the operator **what data to collect next**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OPERATOR WORKFLOW                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Initial Pull(s)                                                 │
│     ├─ WOT sweep on dyno                                           │
│     ├─ Part-throttle sweeps (if eddy current)                      │
│     └─ Street logging for cruise/transients                        │
│                                                                     │
│  2. DynoAI NextGen Analysis                                        │
│     ├─ Mode Detection: "72% of samples are WOT, 3% steady cruise"  │
│     ├─ Surface Builder: Sparse coverage below 60 kPa MAP           │
│     ├─ Spark Valley: Rear cylinder valley 4° deeper than front     │
│     ├─ Cause Tree: "Tip-in hesitation likely transient fuel"       │
│     └─ Next-Test Plan:                                             │
│         • "Fill cells 2500-4000 RPM × 40-60 kPa (14 cells empty)"  │
│         • "Controlled roll-on sweep to quantify transient lag"     │
│         • "Repeat WOT at stable IAT to separate thermal trims"     │
│                                                                     │
│  3. Operator Executes Recommended Tests                            │
│     ├─ If eddy current: Hold RPM, sweep throttle through gaps     │
│     ├─ If inertia: Street logging at part throttle                │
│     └─ Controlled transient maneuvers                              │
│                                                                     │
│  4. Re-analyze with Combined Data                                  │
│     └─ Cause tree updates: hypotheses confirmed or eliminated      │
│                                                                     │
│  5. Apply Corrections When Confidence Sufficient                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Will Dyno Control Be in the Code?

**Not in the current spec.** DynoAI remains analysis-only. Here's why:

1. **Hardware fragmentation** — Dynojet, Mustang, Dynapack, Superflow, Land & Sea all have different control interfaces. Supporting them all is a massive undertaking.

2. **Safety liability** — Automated dyno control that commands throttle position and brake load is safety-critical. A bug could over-rev or overheat an engine.

3. **Operator judgment** — The human needs to watch temps, listen for knock, smell for problems. Full automation removes that safety layer.

---

## 5. Potential Future: Dyno Integration

There's a logical future extension where DynoAI produces test plans that dyno control software could execute:

```
┌─────────────────────────────────────────────────────────────────┐
│              POTENTIAL FUTURE: DYNO INTEGRATION                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  NextGen Analysis produces:                                     │
│    next_tests: [                                                │
│      { rpm: 3000, map_target: 50, dwell_seconds: 5 },          │
│      { rpm: 3500, map_target: 50, dwell_seconds: 5 },          │
│      { rpm: 4000, map_target: 50, dwell_seconds: 5 },          │
│      ...                                                        │
│    ]                                                            │
│                                                                 │
│  Dyno control software (separate system) could:                │
│    1. Import test plan from DynoAI                             │
│    2. Execute automated sweep with operator supervision        │
│    3. Export logs back to DynoAI                               │
│                                                                 │
│  DynoAI stays analysis-only; dyno software handles control     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

This keeps the safety boundary clear: **DynoAI recommends, dyno software executes under operator supervision.**

---

## 6. Practical Considerations for Shop Setup

### Inertia Dyno (Dynojet 250i, etc.)

**Best for:**
- Lower cost, faster turnaround for WOT tuning
- "Peak power" customers who just want WOT dialed

**DynoAI behavior:**
- NextGen will flag that you need street logging for part-throttle
- Coverage maps will show diagonal stripe (high MAP only)

### Eddy Current (Mustang MD-AWD, Dynapack, etc.)

**Best for:**
- Systematic cell-by-cell coverage
- Drivability tuning, emissions work, full calibrations
- True steady-state measurements for VE accuracy

**DynoAI behavior:**
- NextGen can guide you through a complete table fill
- Coverage maps can show full grid population

### Hybrid Approach (Common Practice)

Many shops use:
- Eddy current for deep tuning work
- Street logging for real-world transient validation
- DynoAI merges both data sources and tracks coverage across sessions

---

## 7. NextTestPlan Output Format

The `TestStep` in the spec outputs human-readable guidance:

```python
@dataclass
class TestStep:
    name: str                    # "Fill mid-load cells"
    goal: str                    # "Increase VE confidence in cruise region"
    constraints: str             # "IAT < 40°C, ECT > 80°C"
    rpm_range: tuple[int, int]   # (2500, 4000)
    map_range: tuple[int, int]   # (40, 60)
    test_type: str               # "steady_state_sweep" | "wot_pull" | "transient_rolloff"
    required_channels: list[str] # ["afr_meas_f", "afr_meas_r", "knock"]
    success_criteria: str        # "≥5 samples per cell, variance < 0.3 AFR"
    risk_notes: str              # "Monitor knock at 3500+ RPM"
```

This is **human-readable guidance**, not machine control commands. The operator reads the plan and decides how to execute it on their specific dyno setup.

---

## 8. Summary

| Aspect | Current State | NextGen Adds |
|--------|---------------|--------------|
| Analysis | VE correction math | Mode detection, cause trees, coverage tracking |
| Output | Correction tables | Tables + next-test plans + hypothesis rankings |
| Dyno control | None (post-processing only) | None (still post-processing) |
| Operator role | Run tests, apply corrections | Run targeted tests based on AI guidance |

DynoAI enhances the operator's decision-making without replacing their judgment or taking control of safety-critical hardware.

---

*End of Document*
