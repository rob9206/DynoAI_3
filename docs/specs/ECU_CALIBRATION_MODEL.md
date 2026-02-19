# ECU Calibration and Combustion Control Model

**Integration Strategy for DynoAI Next-Generation Tuning Workflows**

**Target Platform:** Harley-Davidson 2017 Low Rider S (Delphi ECU)

**Audience:** AI systems and human engineers requiring deep understanding of VE tables, spark maps, knock limits, and control-loop interactions in OEM motorcycle ECU calibration.

---

## 1. System Boundary and Controllability

### 1.1 Calibration versus Firmware Boundary

The Delphi ECU contains two distinct regions:

- **Executable firmware:** Implementing estimation, control, diagnostics, and safety logic
- **Calibration data:** Tables and scalars that parameterize that logic

VE correction tables and ignition timing tables belong to calibration data, not executable logic. This distinction is fundamental to understanding what can and cannot be modified through supported toolchains.

### 1.2 Security Constraints

Calibration regions are cryptographically protected and validated during flashing. Attempting raw firmware modification by patching code, bypassing checksums, or disabling security measures is neither practical nor safe for experimentation. Within legal and safe boundaries, the realistic control surface consists of calibration-layer editing via supported toolchains that handle validation automatically.

### 1.3 Practical Consequence

Absolute control over how the ECU computes VE or how knock control works internally is not attainable on the stock Delphi ECU. However, meaningful control over fueling and ignition behavior is achievable by modifying the calibration tables the ECU already uses at runtime. This represents real engineering control, even if it falls short of firmware-level access.

---

## 2. Core Runtime Model

### 2.1 Aircharge Estimation

The ECU computes cylinder air mass per combustion event through a layered model:

```
Aircharge = BaseAirModel × VE_correction × transient_modifiers × environmental_modifiers
```

- **Base air model:** Uses speed-density logic with inputs including RPM, MAP, IAT, displacement, and barometric terms
- **VE table:** Functions as a correction surface, not pure textbook volumetric efficiency. Values exceeding 100% are normal because VE acts as an empirical correction factor
- **Per-cylinder operation:** On V-twins, with separate front and rear corrections

### 2.2 Fueling Computation

Once aircharge is estimated, fuel mass is computed by dividing aircharge by the target lambda. The ECU then applies layered modifiers:

| Modifier | Purpose |
|----------|---------|
| Temperature enrichment | Warmup and IAT effects |
| Transient fueling | Acceleration enrichment, wall-wetting compensation |
| Closed-loop O2 feedback | Corrections when enabled and within authority limits |
| Power enrichment | WOT fueling targets (often open-loop or reduced feedback) |

**Operational Implication:** In closed-loop regions, VE errors can be partially masked by O2 corrections. In open-loop and high-load regions, VE directly determines delivered AFR and therefore knock margin and torque output.

### 2.3 Ignition Computation

Spark timing is not a single table lookup:

```
Final_Spark = Base_Spark + Adders(IAT, ECT, baro, state) - Knock_Retard - Torque_Limiters
```

- The calibration-exposed spark table represents only the baseline
- Knock control retains authority even in race contexts
- Final spark is time-varying due to knock events and thermal modifiers

---

## 3. VE and Spark Coupling Mechanisms

### 3.1 Spark Affects Apparent VE

Advancing spark increases torque for the same air mass by improving combustion phasing and efficiency. Because the ECU does not directly measure torque, observed outcomes (acceleration, inferred load changes, trim behavior) can make it appear that airflow changed.

**Common Misinterpretation:** A spark change looks like a VE change in logs.

### 3.2 VE Errors Distort Spark Optimization

When aircharge estimation is wrong:

1. Delivered AFR deviates from intended targets (especially in open-loop)
2. Cylinder pressure and burn temperature change
3. Knock propensity changes, forcing dynamic spark retard
4. Spark tuning becomes unstable until fueling/air estimation is stabilized

**Professional Heuristic:** Stabilize VE and fueling first, then optimize spark.

### 3.3 Knock Creates Tight Feedback Coupling

Knock depends on:
- Cylinder pressure
- Mixture strength
- Charge temperature

These depend on:
- Aircharge (from VE model)
- AFR
- Spark phasing

A VE change can increase knock → causing spark retard → reducing torque → indirectly altering the operating point and observed fueling needs. This loop is always active in high-load regions.

---

## 4. VE Table Axis Interpretation

### 4.1 Table Structure

The VE table is a two-dimensional correction surface:

| Axis | Role | Interpretation |
|------|------|----------------|
| RPM (X) | Phase and resonance index | Which resonance regime the engine is in |
| MAP (Y) | Load proxy and intake dynamics proxy | Cylinder filling and dynamic regime |

The ECU interpolates between cells continuously—gradients between cells matter more than individual cell values.

### 4.2 MAP Axis Meaning

MAP is used as a proxy for cylinder filling and load, but on a Harley V-twin it is distorted by:

- Intake and exhaust pressure waves
- Reversion from cam overlap
- Sensor placement and filtering lag

**MAP Regions:**

| Region | Characteristics |
|--------|-----------------|
| Low MAP | Counterintuitive corrections due to pulsation, reversion, poor signal quality |
| Mid MAP | Smoother and more linear |
| High MAP | Strong coupling to scavenging and ram effects; large AFR consequences in open-loop |

### 4.3 RPM Axis Meaning

RPM indexes which resonance regime the engine is in:

- VE peaks and dips form where pressure waves align or misalign with valve events
- VE is not monotonic with RPM
- Sharp features in the VE surface can be real resonance artifacts, not tuning mistakes
- The table is not separable (same MAP at different RPM yields different airflow per cycle)

### 4.4 Cylinder Specificity

Front and rear cylinders need separate VE correction because of:

1. **Thermal asymmetry:** Rear often runs hotter
2. **Scavenging differences:** Different exhaust timing effects
3. **Intake/exhaust dynamics:** Different effective paths

This separation is not optional but fundamental to V-twin architecture.

---

## 5. Spark Surface Behavior

### 5.1 Base Spark Surface Shape

| MAP Region | Typical Behavior | Reason |
|------------|------------------|--------|
| Low MAP | High advance plateau | Low cylinder pressure, large knock margin, efficiency optimization |
| Mid MAP | Transition downward | Load increases, drivability/torque smoothness constraints |
| High MAP | Lower base timing | High cylinder pressure, shrinking knock margin, state-dependent from knock retard |

### 5.2 The Spark Valley at WOT

At high MAP, the spark surface often forms a **valley** around the torque peak band:

1. Trapped mass peaks from VE and resonance effects
2. Peak pressure increases for a given spark angle
3. Knock margin is lowest where cylinder pressure is highest
4. Small advance changes shift peak pressure earlier, crossing knock threshold rapidly
5. At higher RPM past VE peak, trapped mass falls and knock margin can recover
6. Results in downward bend then partial recovery in spark surface

### 5.3 Per-Cylinder Asymmetry

The rear cylinder often exhibits:

- Earlier onset of knock-limited behavior
- Deeper and wider effective valley
- Slower recovery under heat soak

Therefore there are effectively **two time-varying spark surfaces** (front vs rear), not one unified surface.

---

## 6. Operating Regimes and Dominant Control Loops

### 6.1 Idle and Very Low MAP

At idle:
- Spark timing is frequently used as a fast actuator for RPM stability
- When RPM drops: ECU advances spark briefly to add torque
- When RPM rises: ECU retards spark to reduce torque
- MAP is noisier and less representative due to pulsation/reversion
- O2 feedback may be limited to prevent hunting
- Coupling is dominated by stability and sensor interpretation

### 6.2 Light Cruise and Low Load

If MAP is used as the primary load signal in a reversion-prone region:

```
MAP noise → AFR oscillations → Torque oscillations → 
Spark stabilization responses → Further exhaust O2/trim perturbation
```

A blended speed-density and alpha-N architecture mitigates this by reducing MAP authority at low load and using TPS as a stable load proxy.

### 6.3 WOT and High MAP

At wide open throttle:
- Closed-loop lambda authority is typically reduced or disabled
- VE accuracy largely determines delivered AFR
- Knock control becomes the primary constraint shaping final spark
- Small air and fuel modeling errors dramatically change observed spark valley depth/width

---

## 7. Control System Layers That Reshape Table Behavior

### 7.1 Filtering

MAP and TPS are filtered before use:
- Filtering adds phase lag
- Lag can create apparent instability even with stable tables if feedback loops chase delayed signals
- A stable table can look unstable if the measurement feeding it is noisy or delayed

### 7.2 Transient Fueling

Injected fuel does not instantly become cylinder fuel due to surface wetting and evaporation:

| Event | Problem | Result |
|-------|---------|--------|
| Tip-in | Air rises immediately, fuel delivery lags | Lean spike risk |
| Tip-out | Air drops immediately, fuel film continues evaporating | Rich spike risk |

These transients can masquerade as VE errors in logs.

---

## 8. Programmable ECU Advantages

### 8.1 Why Programmable ECUs Enable Better Control

On a programmable ECU (e.g., Haltech, Link, AEM, MegaSquirt):

- The hidden control blocks (filtering, blending, transient film modeling, lambda controller, knock controller) become explicit and configurable
- This enables absolute control experiments without altering OEM firmware internals

### 8.2 Blended Load Model

Many programmable ECUs use a blended load model:

```
Load_blend = α × MAP_based_load + (1 - α) × TPS_based_load
```

Where α varies with RPM, TPS, MAP, and operating state:
- Favors TPS at low load (with reversion)
- Favors MAP at mid and high load

---

## 9. Fueling Pipeline Detail

```
Lambda_target ← Table lookup (RPM × Load)
Base_fuel_mass = Blended_aircharge / Lambda_target
Injector_pulsewidth = Injector_model(fuel_mass) + Battery_deadtime
```

**Corrections Applied:**
- Warmup enrichment
- IAT fuel correction
- Barometric correction
- Per-cylinder trims
- Transient fuel model (accel enrichment, optional wall-wetting film model)
- Closed-loop lambda control (bounded PI-like correction with authority limits)

---

## 10. Spark Pipeline Detail

```
Base_spark ← Table lookup (RPM × Load × Cylinder)
Adders = IAT_trim + ECT_trim + Idle_stabilizer + Transient_shaping
Knock_retard = f(windowed_detection, threshold_table, retard_step, decay_rate, cylinder_sensitivity)
Final_spark = Base_spark + Adders - Knock_retard
```

---

## 11. Crank-Angle Pressure Trace View

### 11.1 Central Object

The ECU is implicitly trying to achieve stable combustion, high torque, and no knock by controlling:

- **Compression pressure:** Set by trapped mass
- **Combustion pressure rise:** Set by phasing and burn rate

Cylinder pressure versus crank angle is the fundamental quantity being managed even though it is not directly measured.

### 11.2 Spark as Phasing Control

Spark timing shifts the heat-release curve along crank angle:

- **CA10, CA50, CA90:** Conceptual heat release milestones
- **Peak pressure angle:** Key marker
- **MBT timing:** Places these markers to maximize torque without pushing peak pressure too early

### 11.3 Fueling Alters Burn Speed and Knock Margin

Mixture affects burn rate and end-gas conditions:
- Faster burn → effective advance
- Slower burn → effective retard
- Leaner/hotter → reduced knock margin
- Richer/cooler → increased knock margin (with power tradeoffs)

### 11.4 Knock Detection Windows

Knock systems detect high-frequency vibration in specific crank-angle windows:
- Near and after peak pressure
- Earlier pressure rise increases likelihood of knock window triggers
- Links knock detection directly to combustion phasing

---

## 12. Canonical Pressure Trace Failure Modes

### 12.1 Too Advanced / Knock-Prone

**Signatures:**
- Early peak pressure
- Frequent knock events
- Knock retard repeatedly invoked
- Spark becoming noisy and depressed in torque peak band

### 12.2 Too Retarded / Overheated Exhaust Tendency

**Signatures:**
- Late pressure rise
- Softer torque output
- Potential for higher exhaust temperatures
- Engine feeling flat rather than sharply pulled by knock intervention

### 12.3 Mixture Unstable / Cyclic Variation

**Signatures:**
- Cycle-to-cycle torque scatter
- Idle instability
- Noisy O2 readings
- Oscillating trims
- Busy spark stabilization activity

---

## 13. DynoAI Integration Strategy

### 13.1 Integration Objectives

1. Encode VE-spark-knock-transient-thermal coupling explicitly in analysis pipeline
2. Enforce proper tuning order (VE stabilized before spark optimized)
3. Provide causal diagnosis rather than just error metrics
4. Generate structured next-test plans based on coverage and confidence
5. Maintain DynoAI's deterministic math and apply-rollback guarantees

### 13.2 New Core Modules

#### Mode Detection Module

Classifies each log sample into operating states:

| State | Eligibility |
|-------|-------------|
| `steady_state` | VE surface correction |
| `transient_tip_in` / `transient_tip_out` | Transient fuel modeling |
| `closed_loop_like` vs `open_loop_like` | Affects whether VE error is masked |
| `heat_soak_suspect` | Thermal overlay but not steady VE |
| `knock_active` / `knock_recovering` | Timing safety logic |
| `idle_stabilization` | Spark acting as torque actuator |

#### Surface Builders Module

Produces next-generation grids beyond current VE correction matrices:

**Fueling Surfaces:**
- `VE_error_surface` (steady-state data only)
- `lambda_target_surface` (commanded values)
- `lambda_delivered_surface` (actual outcomes)
- Confidence surfaces (hit counts, variance, condition spread)

**Spark and Knock Surfaces:**
- `base_spark_proxy_surface`
- `final_spark_surface`
- `knock_rate_surface` (events per cell)
- `knock_retard_surface` (mean and max per cell)
- `valley_indicator_surface` (midrange high-load band where knock-limited timing dominates)

#### Cause Tree Module

Deterministic diagnosis module consuming surfaces and state tags:

**Output:**
- `symptoms_detected`
- `cause_hypotheses` (with confidence scores and evidence)
- `recommended_action_class`:
  - Transient model
  - Thermal overlay
  - Spark safety delta
  - Blend strategy hint
  - Data collection plan

### 13.3 Staged Workflow Enhancement

| Stage | Purpose | Output |
|-------|---------|--------|
| 0 | Data quality assurance and column normalization | QA report, excluded segments |
| 1 | Thermal sanity analysis (detect heat soak) | thermal_overlay_factor, exclude recommendation |
| 2 | Transient model learning (tip-in/tip-out) | transient_compensation_recommendations |
| 3 | Steady-state fueling analysis (non-soak only) | VE delta surfaces per cylinder with confidence maps |
| 4 | Spark and knock safety shaping | Conservative spark deltas with clamps, valley band annotation |
| 5 | Export package and rollback bundle | Manifest recording every stage, version, and applied gating |

### 13.4 API and UI Extensions

**API Extensions:**

New `nextgen_analyze` endpoint returning:
- Surfaces
- Cause tree
- Next-test plan
- Export artifacts

Extended `AutoTuneSession` dataclass:
- `mode_tags_summary`
- `thermal_profile` with `soak_events`
- `transient_result` with events and recommended tables
- `knock_analysis` per cylinder
- `spark_corrections` per cylinder
- `next_test_plan`
- `cause_tree`

**UI Extensions:**

New **NextGen tab** in JetDrive:
- **Spark valley view:** Overlaying knock-rate and knock-retard on RPM/MAP grid per cylinder
- **Transient events timeline:** Highlighting where transients triggered knock retard
- **Thermal robustness view:** Heat-soak-suspect run fraction
- **Cause tree panel:** Deterministic explanation and disambiguation guidance
- **Next-test planner:** Coverage gaps and proposed dyno actions

### 13.5 AI Integration Strategy

```
┌─────────────────────────────────────────────────────────────┐
│              DETERMINISTIC ENGINE                           │
│  Computes corrections and diagnostics with full provenance │
│  Outputs structured JSON as ground truth                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              OPTIONAL AI LAYER                              │
│  Generates narrative explanations, operator instructions,  │
│  and training documentation                                │
│  NEVER performs calculations or determines corrections     │
│  Only interprets and explains results                      │
└─────────────────────────────────────────────────────────────┘
```

This maintains DynoAI's core guarantee of deterministic, reproducible, bit-for-bit consistent outputs while adding intelligent assistance for interpretation and planning.

### 13.6 Safety and Governance

| Mechanism | Purpose |
|-----------|---------|
| Human-in-the-loop gating | User confirmation before applying changes |
| Audit trail | Records run IDs, inputs, outputs, and code versions |
| Policy gates | Track-only/dyno-only mode flags, mandatory acknowledgements, hard delta limits |
| Abort logic | Stops recommending advance if knock retard or temperatures exceed thresholds |
| Security boundary | Only operates on calibration inputs via supported toolchains |

---

## 14. Summary for AI Reasoning

VE and spark tables should be treated as parts of a **layered estimation-and-control system**, not as independent truth surfaces.

**Key Relationships:**
1. Aircharge estimation (base model × VE correction) → determines fueling
2. Fueling and thermal state → determine knock margin
3. Knock control → reshapes final spark dynamically (especially where VE peaks and cylinder pressure is highest)

**Regional Dominance:**
- Low-load regions: Dominated by sensor dynamics, filtering, and stability control
- High-load regions: Dominated by open-loop fueling accuracy and knock constraints

**Why Programmable ECUs Matter:**
A programmable ECU makes the hidden blocks explicit (filtering, blending, transient film modeling, lambda controller, knock controller)—which is why it is the correct environment for absolute control experiments without altering OEM firmware internals.

**Key Insight for DynoAI:**
Observed behavior is the superposition of static calibration surfaces and time-varying control loops. Effective tuning requires:
1. Separating these effects through proper state classification
2. Enforcing correct tuning order
3. Providing causal diagnosis rather than just error magnitude

The integration strategy maintains deterministic math while adding physics-informed reasoning that matches how the ECU actually operates at runtime.

---

*End of Document*
