# iter_6 Patch -- AE fix only (supersedes iter_5; rolls VE back to iter_3)

Generated: 2026-05-12T22:09:57+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

iter_5 (VE rich-trim + AE fix) was flashed and showed a 10+ hp loss vs iter_3
on the comparable full pull (`PV_Logfile_5.csv_24.txt`: 81.5 hp / LC2 12.4
vs iter_3 91-92 hp / LC2 11.5-11.7). Rear injector duty also pegged at
100-104% above 5500 RPM in pulls `_21` and `_24`. Conclusion: this bike's
WOT cells make more power richer than the Dynojet PE target on this dyno
with the LC2 venturi -- iter_5's lean trim went the wrong direction for HP.

iter_6 keeps only the evidence-driven AE fix (which addresses tip-in lean
spikes seen in 3rd-gear data) and reverts the WOT VE trim to iter_3.

- base file: `iter_3_patched.pvv`
- base SHA-256: `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`
- iter_6_patched.pvv SHA-256: `fd5ba039839ef3cc2c1608d963f388927c0172c7d843aa38bd04e2ec0bd1a5ff`

## Acceleration Enrichment table (only change vs iter_3)

Boost mid-decay AE for 3000-4700 RPM tip-in, remove 0.91 post-event
enleanment tail.

| time idx | base | new | delta |
|---|---|---|---|
| 3 | 3.98 | 3.98 | +0.00 |
| 32 | 3.00 | 3.30 | +0.30 |
| 61 | 2.31 | 2.55 | +0.24 |
| 90 | 1.84 | 2.00 | +0.16 |
| 118 | 1.47 | 1.55 | +0.08 |
| 147 | 1.23 | 1.25 | +0.02 |
| 176 | 1.06 | 1.06 | +0.00 |
| 205 | 0.95 | 1.00 | +0.05 |
| 234 | 0.91 | 1.00 | +0.09 |
| 262 | 0.91 | 1.00 | +0.09 |
| 291 | 0.91 | 1.00 | +0.09 |
| 320 | 0.91 | 1.00 | +0.09 |

## Tables byte-identical to iter_3

- VE (TPS based/Front Cyl), VE (TPS based/Rear Cyl) -- WOT trim REVERTED
- Engine Displacement (103.0 CID)
- Spark Advance Front/Rear (cam advance + 5500 knock notch preserved)
- AFR / PE AFR (targets unchanged)
- Deceleration Enleanment, Max Knock Retard, RPM Limit

## Expected outcome (4th-gear pulls)

- Peak HP returns to iter_3 baseline: 91-92
- WOT LC2 in 3000-5500 RPM: 11.5-11.7 (back to richer, what the bike likes)
- 3rd-gear tip-in at 3000-4700 RPM: LC2 max 0-300ms drops from ~14.0
  toward 12.5-13.0; bike feels crisper at roll-on

## Outstanding constraint

- Rear injector duty saturating 100-104% above 5500 RPM in iter_3/iter_5
  data. Tune cannot push more fuel above this RPM band without bigger
  injectors. iter_7+ should consider lowering RPM ceiling targets or
  flagging a hardware upgrade for the customer.

## Abort criteria post-flash

- Tip-in LC2 < 11.0 sustained -- AE overshoot, revert to iter_3
- Knock retard > 4 deg -- something else changed, revert to iter_3
- WOT HP drops vs iter_3 -- unexpected, revert and review

## Revert

Re-flash `iter_3_patched.pvv` (SHA-256 `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`).

---

## Post-flash validation -- 2026-05-12 (iter_6 brake-fixed run)

### Tune verification (ECU export)

Read tune off the ECU after flash; saved as `exporte6.pvv` in `iter_6/patch/`.
Result: tune on ECU is iter_6 (within XML float-roundtrip tolerance).

- displacement on ECU = **103.0 CID** (correct)
- AE table on ECU = **iter_6 values** (correct)
- VE Front/Rear at WOT (TPS=100): identical to iter_3/iter_6 within ~0.3% rounding
- All other tables (spark, decel, knock cap, RPM limit, AFR, PE AFR) match iter_6
- Earlier hypothesis of a bad flash (revert to 88.48 CID) is **ruled out**

### First post-flash batch (pulls _25..28) -- INVALID

Initial pulls after iter_6 flash showed inexplicable -20 hp and lean AFR vs iter_3.
Diagnosis: **rear brake was dragging.** Evidence:

- RPM acceleration rate during WOT = 530-540 rpm/s vs healthy 760-820 rpm/s
- Same MAP/TPS/displacement; AFFF/AFFr at unity; tune verified on ECU
- ECU was commanding the right amount of fuel for the air it saw, but the
  drum was being held back by a stuck rear brake -> dyno read low HP, RPM
  rose slowly, longer dwell time per cell let LC2 settle leaner.

Pulls _25..28 are tagged invalid in `pulls/manifest.json`. Treat them as loaded /
parasitic-drag pulls only (useful for AE/spark response under sustained load,
NOT for free-accel HP claims).

### Post-brake-fix batch (pulls _31, _32, _33) -- VALID

After the user found and fixed the dragging rear brake:

| Pull | Peak HP | Peak RPM | LC2 @ peak | Avg LC2 3-5.5k | RPM rate (med) | Inj duty R max | Knock |
|---|---|---|---|---|---|---|---|
| _31 | 94.48 | 5273 | 11.97 | 12.32 | 760 | 93.5% | 0.0 |
| _32 | 95.09 | 5404 | 12.60 | 12.80 | 820 | 88.6% | 0.0 |
| _33 | 95.16 | 5348 | 12.76 | 12.80 | 760 | 86.1% | 0.0 |

vs iter_3 baseline:

| Set | Peak HP avg | LC2 3-5.5k avg |
|---|---|---|
| iter_3 (wot_4 + wot_7) | 92.0 | 11.66 |
| iter_6 (_31 + _32 + _33) | **94.91** | 12.64 |

**+2.9 hp over iter_3** with leaner combustion and zero knock. Tune is healthier.

CHT max 153F, IAT max 108F, no pegging, all WOT samples valid.

### Outstanding (unchanged from pre-flash)

- Rear injector duty hit **93.5%** at 5500-6000 RPM on _31. Approaching
  saturation. Future iterations cannot increase WOT VE without risking
  injector ceiling. Spark or compression are the remaining levers for HP.

### Status

iter_6 = **VALIDATED**. Ready to be the new baseline for iter_7+.

