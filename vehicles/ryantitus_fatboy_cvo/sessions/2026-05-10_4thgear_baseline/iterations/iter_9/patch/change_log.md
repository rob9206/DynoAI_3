# iter_9 Patch -- decel rich-fix on top of iter_8

Generated: 2026-05-12T23:45:41+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

Cruise data from iter_8 pulls (`_41..44`, 3145 steady-state samples) showed:
- Real cruise at MAP 50-70 kPa is on AFR target
- Decel/closed-throttle cells at MAP 30-40 kPa run 1.5-2.5 AFR RICH
  (LC2 ~12.1-12.9 vs target ~14.5-14.7)

iter_9 fixes the decel rich condition with two coordinated changes:

- base file: `iter_8_patched.pvv`
- base SHA-256: `bdcd004fd9d333e6d3d90e39d37c574e4b294a5a02aa9bb1855ebfcc8c50dd21`
- iter_9_patched.pvv SHA-256: `8bd9e48b2a6a95350a2d0f5ba420998f12201bbe9de1d0963e007b83f061c294`

## Change 1: Deceleration Enleanment table

Set decel multiplier to 0.92 at operating-temp columns (CHT 90-320 F).
Cold columns (CHT 3, 32, 61 F) kept at 1.0 so cold engine does not stall.

| temp F | base | new | delta |
|---:|---:|---:|---:|
| 3 | 1.00 | 1.00 | +0.00 |
| 32 | 1.00 | 1.00 | +0.00 |
| 61 | 1.00 | 1.00 | +0.00 |
| 90 | 1.00 | 0.92 | -0.08 |
| 118 | 1.00 | 0.92 | -0.08 |
| 147 | 1.00 | 0.92 | -0.08 |
| 176 | 1.00 | 0.92 | -0.08 |
| 205 | 1.00 | 0.92 | -0.08 |
| 234 | 1.00 | 0.92 | -0.08 |
| 262 | 1.00 | 0.92 | -0.08 |
| 291 | 1.00 | 0.92 | -0.08 |
| 320 | 1.00 | 0.92 | -0.08 |

## Change 2: VE (TPS based) low-TPS decel trim

Trim VE by 7% at decel-zone cells:
- RPM rows: 1500 - 5000
- TPS columns: [0.0, 2.0, 5.0, 7.0, 10.0]
- Front cells changed: 33
- Rear cells changed: 33

Combined effect: 0.92 * 0.93 = 0.856 effective AFR multiplier on decel cells,
matching the ~0.85 the data shows is needed.

Top 20 VE changes by absolute delta:

| cylinder | RPM | TPS | base | new | delta | delta_pct |
|---|---:|---:|---:|---:|---:|---:|
| rear | 4000 | 10 | 120.79 | 112.33 | -8.46 | -7.00% |
| rear | 2250 | 10 | 116.89 | 108.70 | -8.18 | -7.00% |
| rear | 3500 | 10 | 116.30 | 108.16 | -8.14 | -7.00% |
| rear | 2000 | 10 | 115.43 | 107.35 | -8.08 | -7.00% |
| rear | 4500 | 10 | 115.34 | 107.26 | -8.07 | -7.00% |
| front | 4000 | 10 | 114.65 | 106.62 | -8.03 | -7.00% |
| rear | 2500 | 10 | 114.18 | 106.18 | -7.99 | -7.00% |
| rear | 5000 | 10 | 110.95 | 103.19 | -7.77 | -7.00% |
| front | 3500 | 10 | 110.94 | 103.18 | -7.77 | -7.00% |
| front | 4500 | 10 | 108.95 | 101.32 | -7.63 | -7.00% |
| rear | 3000 | 10 | 108.86 | 101.24 | -7.62 | -7.00% |
| rear | 1750 | 10 | 108.30 | 100.72 | -7.58 | -7.00% |
| rear | 2750 | 10 | 107.66 | 100.12 | -7.54 | -7.00% |
| rear | 2250 | 5 | 107.58 | 100.05 | -7.53 | -7.00% |
| rear | 4500 | 5 | 106.08 | 98.65 | -7.43 | -7.00% |
| front | 2250 | 10 | 106.03 | 98.61 | -7.42 | -7.00% |
| front | 2000 | 10 | 105.86 | 98.45 | -7.41 | -7.00% |
| rear | 2000 | 5 | 105.73 | 98.33 | -7.40 | -7.00% |
| front | 2500 | 10 | 104.79 | 97.45 | -7.33 | -7.00% |
| rear | 4000 | 5 | 104.27 | 96.98 | -7.30 | -7.00% |

## Tables byte-identical to iter_8

- Spark Advance Front/Rear (iter_8 +2 deg WOT preserved)
- Engine Displacement (103.0 CID)
- Acceleration Enrichment (iter_6 AE fix preserved)
- AFR / PE AFR
- Max Knock Retard (4 deg cap), RPM Limit

## Expected outcome

- Cruise at MAP 50-70 kPa: unchanged from iter_8 (already on target)
- Decel / coast (MAP 30-40 kPa): LC2 should rise from ~12.5 toward ~13.5-14.0
- Less decel pop on closed-throttle deceleration
- WOT power: identical to iter_8 (94.2 hp avg)
- Tip-in transient: unchanged (AE table preserved)

## Pull plan

- Coast down test: roll on, then snap closed throttle from 4000-5000 RPM
  in 4th gear; LC2 should not drop below 13.0
- Slow cruise at 2500-3500 RPM, light throttle: LC2 13.0-13.7
- Full WOT pull: should match iter_8 (94+ hp, no knock)

## Abort criteria

- Engine stalls or stumbles when chopping throttle: revert iter_8 (cold cells too lean?)
- Lurch on tip-out: revert iter_8 (decel too aggressive)
- WOT power drops vs iter_8: should not happen (WOT VE/spark untouched), but revert if so

Revert file: `iter_8_patched.pvv` (SHA-256 `bdcd004fd9d333e6d3d90e39d37c574e4b294a5a02aa9bb1855ebfcc8c50dd21`).