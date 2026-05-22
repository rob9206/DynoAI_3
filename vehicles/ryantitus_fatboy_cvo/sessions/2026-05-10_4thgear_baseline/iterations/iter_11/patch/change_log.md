# iter_11 Patch -- directed cruise VE trim from measured AFR

Generated: 2026-05-13T00:08:29+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

iter_9 cruise pulls (`_46/47/48`, 1099 steady-state samples) showed the
loaded dyno hitting cells at TPS 5-25% RPM 1.75-4.5 still rich after iter_9
(which only trimmed TPS 0/2/5/7/10 by fixed -7%).

- base file: `iter_9_patched.pvv`
- base SHA-256: `8bd9e48b2a6a95350a2d0f5ba420998f12201bbe9de1d0963e007b83f061c294`
- iter_11_patched.pvv SHA-256: `7041f5c40453b187d3b0572f0835bef950dc3a40b8a219aecc006dd726ed80ec`

## Strategy

Per-cell directed VE trim using measured AFR error:
- Min hits per cell: 5
- Apply only if measured correction < 0.97 (lean-only, never enrich)
- RPM scope: 1.5 - 5.5 (RPM x 1000)
- TPS columns in scope: [5.0, 7.3, 10.0, 15.0, 20.0, 25.0, 30.0]
- Trim cap: -10% per cell
- Mirror Front and Rear with identical trim

## Result

- Cells trimmed (per cylinder): 22
- Cells where evidence asked for >10% but capped: 34

## Top trims by absolute delta_pct

| cyl | rpm_k | tps | n | LC2 | tgt | corr_meas | applied | base | new | delta_pct |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| front | 3.5 | 7.3 | 19 | 12.16 | 14.63 | 0.831 | 0.900 | 103.71 | 93.34 | -10.00% |
| rear | 2.75 | 10 | 61 | 12.84 | 14.49 | 0.886 | 0.900 | 100.12 | 90.11 | -10.00% |
| rear | 3 | 7.3 | 77 | 12.20 | 14.64 | 0.833 | 0.900 | 100.23 | 90.21 | -10.00% |
| rear | 2.5 | 7.3 | 34 | 13.08 | 14.55 | 0.899 | 0.900 | 101.97 | 91.77 | -10.00% |
| front | 2 | 5 | 57 | 13.04 | 14.57 | 0.895 | 0.900 | 89.31 | 80.38 | -10.00% |
| front | 3.5 | 20 | 22 | 12.08 | 13.95 | 0.866 | 0.900 | 119.80 | 107.82 | -10.00% |
| rear | 2.25 | 5 | 49 | 12.83 | 14.60 | 0.879 | 0.900 | 100.05 | 90.04 | -10.00% |
| front | 2.5 | 7.3 | 34 | 13.08 | 14.55 | 0.899 | 0.900 | 93.16 | 83.85 | -10.00% |
| front | 2.75 | 7.3 | 7 | 11.81 | 14.53 | 0.813 | 0.900 | 100.67 | 90.61 | -10.00% |
| front | 2.75 | 10 | 61 | 12.84 | 14.49 | 0.886 | 0.900 | 94.92 | 85.42 | -10.00% |
| front | 3 | 10 | 94 | 12.52 | 14.46 | 0.866 | 0.900 | 96.65 | 86.98 | -10.00% |
| front | 3.5 | 10 | 32 | 12.33 | 14.52 | 0.849 | 0.900 | 103.18 | 92.86 | -10.00% |
| front | 4 | 15 | 55 | 11.85 | 14.50 | 0.817 | 0.900 | 126.97 | 114.28 | -10.00% |
| rear | 2.75 | 7.3 | 7 | 11.81 | 14.53 | 0.813 | 0.900 | 106.27 | 95.64 | -10.00% |
| rear | 3.5 | 20 | 22 | 12.08 | 13.95 | 0.866 | 0.900 | 125.20 | 112.68 | -10.00% |
| rear | 4.5 | 15 | 87 | 12.21 | 14.61 | 0.836 | 0.900 | 128.39 | 115.55 | -10.00% |
| front | 3.5 | 15 | 103 | 11.78 | 14.17 | 0.831 | 0.900 | 117.41 | 105.67 | -10.00% |
| rear | 3 | 5 | 54 | 12.51 | 14.68 | 0.852 | 0.900 | 88.80 | 79.92 | -10.00% |
| front | 2.5 | 5 | 169 | 12.95 | 14.68 | 0.882 | 0.900 | 87.23 | 78.51 | -10.00% |
| rear | 3 | 15 | 19 | 11.92 | 14.19 | 0.840 | 0.900 | 113.25 | 101.92 | -10.00% |
| rear | 4 | 15 | 55 | 11.85 | 14.50 | 0.817 | 0.900 | 136.04 | 122.44 | -10.00% |
| front | 3 | 5 | 54 | 12.51 | 14.68 | 0.852 | 0.900 | 85.06 | 76.55 | -10.00% |
| rear | 3 | 10 | 94 | 12.52 | 14.46 | 0.866 | 0.900 | 101.24 | 91.12 | -10.00% |
| rear | 3.5 | 10 | 32 | 12.33 | 14.52 | 0.849 | 0.900 | 108.16 | 97.34 | -10.00% |
| front | 2.25 | 5 | 49 | 12.83 | 14.60 | 0.879 | 0.900 | 91.23 | 82.11 | -10.00% |

## Tables byte-identical to iter_9

- Spark Advance Front/Rear (iter_8 +2 deg WOT preserved)
- Engine Displacement (103.0 CID)
- Acceleration Enrichment (iter_6 AE fix preserved)
- AFR / PE AFR
- Max Knock Retard, RPM Limit
- Deceleration Enleanment (iter_9 0.92 preserved)

## Expected outcome

- Cruise AFR at TPS 15-25% on loaded dyno: should rise from LC2 11.8-12.3 toward 13.0-13.5
- Real cruise (MAP 60-70 kPa): unchanged from iter_9
- WOT power: identical to iter_9 (94.2 hp avg)
- Tip-in transient: unchanged

## Pull plan

- Cruise sweep at TPS 10-25% across 2000-4500 RPM (loaded), log
- Snap-closed throttle from 4000+ RPM to validate iter_9 decel fix is live
- One confirmation WOT pull (verify WOT untouched)

## Abort criteria

- Cruise stumble or surging: revert iter_9
- WOT HP drop: revert (should not happen, WOT VE/spark untouched)

Revert file: `iter_9_patched.pvv` (SHA-256 `8bd9e48b2a6a95350a2d0f5ba420998f12201bbe9de1d0963e007b83f061c294`).