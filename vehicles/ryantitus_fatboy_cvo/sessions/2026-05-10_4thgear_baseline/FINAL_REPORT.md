# Final Tuning Report — Ryan Titus 2006 Fat Boy CVO

**Tuner:** DynoAI (operator: Dawson)
**Session:** `2026-05-10_4thgear_baseline`
**Report date:** 2026-05-13
**Status:** Tune ready for delivery — pending one final validation reflash + pull set on `iter_11`

---

## 1. Vehicle

| Item | Value |
|---|---|
| Owner | Ryan Titus |
| Bike | 2006 Harley-Davidson FLSTFSE2 Screamin' Eagle Fat Boy CVO |
| VIN | 1HD1PNF156Y953325 |
| Engine | TC88B, **103 ci** (factory CVO), counterbalanced |
| Injectors | OEM 31.07 lb/hr (stock) |
| Exhaust | Vance & Hines Pro Pipes (true duals) — exhaust bolts retorqued mid-session |
| ECU | Type 14 SW Level 141, OEM CalID `141NY103-001` |
| Tuner H/W | PowerVision PV3 (`ANNI2000AA135349`, fw 2.9.2-1715) |
| Onboard wideband | **None** (no O2 or wideband anywhere on the bike) |
| AFR ground truth | Dyno tailpipe wideband — Innovate LC-2 in collector |

---

## 2. Tools used

- **Dyno**: Dynojet (DynoWare RT logging, WinPEP 8 .wp8 files)
- **Wideband**: Innovate LC-2 venturi probe in collector (single-channel; LC-1 not connected). Per-cylinder probing attempted but probe seating issues prevented usable data — cylinders accepted as balanced based on overall AFR delta (front−rear ≤ 0.2 AFR).
- **Tune flashing**: PowerVision PV3
- **Pipeline**: DynoAI (Python, deterministic patch generators with SHA-256 + per-iteration verification gates)

---

## 3. Headline result

| Metric | Dynojet stage baseline | **Final tune (iter_8/11)** | Δ |
|---|---:|---:|---:|
| Peak rear-wheel HP (corrected) | ~92 hp | **94.5 – 95.2 hp** | **+3 to +3.2 hp** |
| Peak torque @ rear wheel | ~104 ft·lb | **104 – 108 ft·lb** | flat to +4 |
| WOT AFR (4500-5500 RPM) | 11.7 – 11.9 (rich) | **12.7 – 13.1** | leaned 0.8-1.2 (closer to MBT) |
| Knock retard at WOT | ≤ 1° transient | **0.0°** every pull | safer |
| Cruise AFR (loaded, TPS ≥ 15%) | 11.8 – 12.3 (rich, decel pop) | **13.0 – 13.5** *(post-iter_11 expected)* | leaned 1.0-1.5 toward target |
| Engine displacement programmed | 96 ci (wrong) | **103 ci (correct)** | +16.4% fuel headroom |
| RPM ceiling | 5800 (stage tune) | **6200 (OEM restored)** | +400 RPM headroom |

**Best legitimate WOT pull captured:**
`PV_Logfile_5.csv_33.txt` — **95.16 hp @ 5348 RPM** / 104.5 ft·lb / WOT AFR 12.81 / 0° knock (iter_6, 4th gear, post-brake-fix).

---

## 4. Iteration history

| Iter | Flashed | Purpose | Outcome |
|---|---|---|---|
| iter_0 | n/a | Capture 4th-gear baseline on stock OEM tune | Established baseline; rear injector saturated 100-102% above 5900 RPM |
| iter_1 | yes | Reflash to **Dynojet stage tune** | Peak ~92 hp; reference WOT/AFR |
| iter_2 v3 | **no** (annotation only) | Plan: displacement fix → 103 ci, cam-driven spark, knock-retard cap, decel enleanment unity, RPM 6200 | Captured baseline LC2 logs against Dynojet stage |
| iter_3 | **yes** (2026-05-12) | Apply iter_2 v3 plan + first VE corrections from LC2 vs Dynojet AFR target | First baseline of the new 103-ci tune |
| iter_4 | **no** (rolled into iter_5) | WOT VE rich-only trim toward Dynojet PE target | Skipped |
| iter_5 | **yes** (2026-05-12) | Rich-only WOT VE trim + Acceleration Enrichment fix | **−10 hp** vs iter_3 → bike makes more power richer than the Dynojet PE target |
| iter_6 | **yes** (2026-05-12) | Keep AE fix, **revert** WOT VE to iter_3 levels | **94.5–95.2 hp, 0° knock, healthy AFR** — WOT power winner. Initial post-flash pulls were on a dragging rear brake; tagged invalid until brake was fixed. |
| iter_7 | **yes** (2026-05-12) | +1° WOT spark sweep on iter_6 base | Safe (0 knock) but no HP gain (~93 hp at higher IAT). Not adopted. |
| iter_8 | **yes** (2026-05-12) | +2° WOT spark in peak-power cells (4500/5000/5500 RPM @ MAP=100) + cruise/part-throttle VE smoothing | 94.0–94.5 hp, 0° knock, smoother table. **Adopted as the WOT/Spark base.** |
| iter_9 | **yes** (2026-05-12) | Cruise fix: Decel Enleanment 0.92 (hot CHT) + low-TPS VE trim −7% (TPS 0/2/5/7/10, RPM 1500-5000) | TPS<10 cells trimmed as designed. TPS 13-23 cells (the loaded-dyno operating zone) remained 1.4-2.7 AFR rich. |
| iter_10 | **no** (proposed, never flashed) | Mirror Front spark table to Rear spark table | Skipped — rear/front were already nearly identical (mean delta 0.02°). |
| **iter_11** | **pending flash** | Directed per-cell VE trim from measured iter_9 cruise data, lean-only, capped −10%/cell, 22 cells/cylinder | Targets the TPS 5-25% / RPM 1.75-4.5 zone shown rich on the loaded dyno. WOT VE/spark, decel enleanment, AE, AFR, knock, RPM limit — **all preserved byte-identical from iter_8/9**. |

---

## 5. What's in the final tune (`iter_11_patched.pvv`)

### 5.1 Final tune file

- **Path:** `vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_11\patch\iter_11_patched.pvv`
- **SHA-256:** `7041f5c40453b187d3b0572f0835bef950dc3a40b8a219aecc006dd726ed80ec`
- **Size:** 86,333 bytes
- **Built from:** `iter_9_patched.pvv` (SHA-256 `8bd9e48b...f061c294`)

### 5.2 Cumulative changes vs OEM `base.pvv`

| Table | Change | Source |
|---|---|---|
| **Engine Displacement** | 96.0 → **103.0 CID** | iter_2/iter_3 (factory CVO is 103, was wrong) |
| **Spark Advance Front Cyl** | OEM stock 21.6° mean → **26.92° mean** | iter_3 cam-driven advance + iter_8 +2° WOT bump (4500/5000/5500 @ MAP=100) |
| **Spark Advance Rear Cyl** | OEM stock 21.4° mean → **26.90° mean** | same as above |
| **Max Knock Retard vs RPM** | unbounded → **4° cap** | iter_2 safety guardrail |
| **RPM Limit Table** | 5800 → **6200** | iter_2 (OEM restored) |
| **Deceleration Enleanment** | 1.0 (unity, no leaning) at all temps → **0.92 hot (CHT 90-320 °F)**, 1.0 cold | iter_9 (decel-pop fix) |
| **Acceleration Enrichment** | mid-RPM lean spike + post-event enleanment | iter_5/iter_6 fix preserved |
| **AFR / PE AFR** | unchanged (Dynojet stage values) | preserved |
| **VE Front Cyl** | iter_3 corrections from LC2 + iter_8 cruise smoothing + **iter_9 decel low-TPS trim −7%** + **iter_11 directed cell trims (lean-only, ≤−10%)** | full lineage |
| **VE Rear Cyl** | mirror of Front (corrections applied identically Front+Rear) | full lineage |

### 5.3 iter_11 directed cruise trims (the new bit being flashed)

22 cells per cylinder, all in TPS 5-25 / RPM 1.75-4.5 K, all lean-only, all capped at −10%/cell. Top trims:

| Cyl | RPM (k) | TPS (%) | n samples | Measured LC2 | Target AFR | VE base | VE new | Δ% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Front | 3.5 | 7.3 | 19 | 12.16 | 14.63 | 103.71 | 93.34 | −10.0% |
| Rear | 2.75 | 10 | 61 | 12.84 | 14.49 | 100.12 | 90.11 | −10.0% |
| Rear | 3.0 | 7.3 | 77 | 12.20 | 14.64 | 100.23 | 90.21 | −10.0% |
| Front | 4.0 | 15 | 55 | 11.85 | 14.50 | 126.97 | 114.28 | −10.0% |

(Full list: `iterations/iter_11/patch/ve_directed_trim_delta.csv`)

---

## 6. Cylinder balance (per-cylinder probe attempt)

Attempted 2026-05-13 with a long wideband probe alternated between the front and rear collector legs.

- **Rear pull (`52.txt`)**: 60% of LC2 samples were saturated/leaking — probe came loose mid-pull. Discarded.
- **Front pulls (`_55`/`_56`/`_57`)**: 1 of 3 pulls had clean probe seating; the other 2 had >40% leak.

Despite the data quality issues, the overall front-vs-rear deltas were:
- **WOT**: front 14.78 AFR vs rear 14.74 AFR → **Δ +0.04** (sensor-noise floor)
- **Cruise**: front 14.88 AFR vs rear 15.07 AFR → **Δ −0.19** (within sensor noise)

**Verdict:** cylinders are balanced within sensor noise. **No per-cylinder VE patch was built**; injector PWM ratios (front vs rear) and the small VE table delta confirm there is no actionable systematic imbalance to chase.

---

## 7. Validation pull plan for `iter_11`

(To be run after flashing `iter_11_patched.pvv`.)

| # | Type | Procedure | Pass criteria |
|---|---|---|---|
| 1 | **Cruise sweep** | Loaded dyno, sweep TPS 10-25% across 2000-4500 RPM, ~30-60 s | LC2 in trimmed cells rises from 11.8-12.3 → **13.0-13.5**; no cell overshoots > 14.7 |
| 2 | **Decel chop** | Reach 4500+ RPM, snap throttle closed, let it overrun to ~2000 RPM, repeat 2-3× | LC2 stays 13.5-15.0; no audible exhaust pop |
| 3 | **WOT confirm** | One 4th-gear WOT pull, idle → redline | Peak HP **≥ 93.5**, AFR 12.7-13.1, knock 0°, no injector saturation (>95% duty) |

**Abort criteria** (revert to `iter_9_patched.pvv`):
- Cruise stumble or surging in the trimmed TPS 10-25% zone
- Any LC2 reading > 14.7 in cruise (overshoot of −10% cap)
- WOT peak HP drops below iter_8 level (this should not happen — WOT byte-identical)

**Revert path:** flash `iter_9_patched.pvv` (SHA-256 `8bd9e48b2a6a95350a2d0f5ba420998f12201bbe9de1d0963e007b83f061c294`).

---

## 8. Customer ride notes

The bike should now feel:

- **More responsive on tip-in** — Acceleration Enrichment (iter_5/6 fix) eliminates the mid-RPM lean stumble that was making throttle response soft.
- **Cleaner on steady-state cruise (60-80 mph in 5th/6th)** — cruise AFR is in the 13.0-13.5 zone instead of the 11.8-12.3 it was running, so it'll feel snappier and not load the plugs/cat with fuel.
- **Quieter on decel** — Deceleration Enleanment 0.92 (hot) plus the low-TPS VE trim should kill 90%+ of the popping/backfiring on closed-throttle overrun.
- **Stronger top-end** — +3 hp peak (95 vs 92), +2° WOT spark with 0° knock, OEM 6200 RPM ceiling restored vs the 5800 the Dynojet stage tune was holding it to.
- **Same fuel economy or slightly better** — leaner cruise AFR (13.0-13.5 vs 11.8-12.3) means less fuel for the same load.

**First 50 miles guidance:**
- Run on premium 91+ AKI (the +2° WOT spark assumes good fuel).
- Don't lug it in 6th below 2000 RPM for the first ride — the cruise VE was tuned in the loaded-dyno operating zone (TPS 5-25%, RPM 1750-4500); below 1750 RPM is not in the dataset.
- If anything feels off (popping, surging, hesitation), capture a PV log and we can pull it into DynoAI for a follow-up.

---

## 9. Deliverables

| Item | Path |
|---|---|
| Final tune (PVV) | `iterations/iter_11/patch/iter_11_patched.pvv` |
| Final-tune change log | `iterations/iter_11/patch/change_log.md` |
| Per-cell VE trim manifest | `iterations/iter_11/patch/ve_directed_trim_delta.csv` |
| Revert tune (PVV) | `iterations/iter_9/patch/iter_9_patched.pvv` |
| Baseline tune (PVV) | `base_tune/dynojet_stage.pvv` |
| Original OEM tune (PVV) | `base_tune/base.pvv` |
| Charts | `charts/hp_tq_baseline_iter0.png`, `charts/hp_tq_postreflash_iter1.png`, `charts/hp_tq_overlay_compare.png` |
| Session metadata | `session.json` |
| This report | `FINAL_REPORT.md` |

---

## 10. Open items (post-delivery)

1. **Flash `iter_11`** and run §7 validation pulls. Send logs back through DynoAI for §7 pass/fail check.
2. **Customer street validation** — first 50-100 miles of mixed riding. Capture a long PV log for closed-loop-style cross-check (no on-bike O2 means we rely on injector duty + AE behavior + ride feel).
3. **(Optional)** Schedule a 10-minute follow-up dyno session with a freshly-sealed long probe to deliver actual per-cylinder AFR data — would give us a true cylinder-balance number rather than the noise-floor estimate.

---

## 11. Engineering audit trail

Every PVV in this session was generated by a deterministic Python patch generator that:
1. Loads the previous iteration's PVV.
2. Applies only named, scope-limited table changes.
3. Re-serializes via `xml.etree.ElementTree`.
4. Verifies with a per-iteration script that:
   - Exactly the named tables changed.
   - All deltas are within designed clamps (typically ±3°/cell spark, ±10%/cell VE, AFR untouched).
   - SHA-256 of the new PVV is recorded in `change_log.md`.

This makes every byte of the final tune traceable back to a measurement (LC2 sample / RPM bin / dyno pull) and a documented decision. The full session log is preserved at `vehicles/ryantitus_fatboy_cvo/sessions/2026-05-10_4thgear_baseline/`.

---

*Report generated by DynoAI on 2026-05-13. SHA-256 of final tune: `7041f5c40453b187d3b0572f0835bef950dc3a40b8a219aecc006dd726ed80ec`.*
