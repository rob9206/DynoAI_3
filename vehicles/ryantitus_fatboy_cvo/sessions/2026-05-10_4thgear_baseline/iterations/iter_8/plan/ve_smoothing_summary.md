# iter_8 VE Smoothing Proposal (annotate-only)

Base: iter_6_patched.pvv

## Scope

- rows: RPM 1500 -- 5000 (cruise + part-throttle)
- cols: TPS 0% -- 60% (excludes WOT 80/100 columns)

## Algorithm

- 3x3 neighbour mean (center excluded)
- deadband: |residual| < 1.5% of neighbour mean -- skip
- nudge: new = cell - 0.5 * residual (halfway toward neighbours)
- per-cell change cap: ±3.0% of cell base

## Locks (NOT touched, reasons)

- TPS 80% / TPS 100% columns: WOT cells, validated by iter_6 dyno data (95 hp, AFR 12.0-12.8). Smoothing breaks AFR ground truth.
- RPM <= 1000: idle / throttle blip area, no measurement evidence.
- RPM >= 5500: top of rev range; 6500 row is hard-clipped at 81/83.5 rev-limit floor.

## Proposed change counts

### VE (TPS based/Front Cyl)

- cells changed: 87
- avg |delta|: 2.11  max |delta|: 3.99

Top 15 changes by |delta|:

| RPM | TPS | base | new | delta | delta_pct |
|---|---|---|---|---|---|
| 4500 | 20 | 133.10 | 129.11 | -3.99 | -3.00% |
| 4000 | 15 | 130.90 | 126.97 | -3.93 | -3.00% |
| 2750 | 15 | 116.86 | 113.35 | -3.51 | -3.00% |
| 2000 | 30 | 111.10 | 107.77 | -3.33 | -3.00% |
| 4000 | 25 | 127.63 | 124.40 | -3.24 | -2.54% |
| 1750 | 20 | 105.50 | 102.33 | -3.17 | -3.00% |
| 5000 | 60 | 105.50 | 108.67 | +3.17 | +3.00% |
| 2750 | 7 | 103.79 | 100.67 | -3.11 | -3.00% |
| 1750 | 30 | 103.40 | 100.30 | -3.10 | -3.00% |
| 3500 | 5 | 102.85 | 99.76 | -3.09 | -3.00% |
| 3500 | 25 | 121.79 | 118.71 | -3.08 | -2.53% |
| 2250 | 5 | 101.13 | 98.10 | -3.03 | -3.00% |
| 5000 | 10 | 101.00 | 104.03 | +3.03 | +3.00% |
| 2000 | 5 | 99.00 | 96.03 | -2.97 | -3.00% |
| 3000 | 15 | 105.24 | 108.20 | +2.96 | +2.81% |

### VE (TPS based/Rear Cyl)

- cells changed: 92
- avg |delta|: 2.24  max |delta|: 4.21

Top 15 changes by |delta|:

| RPM | TPS | base | new | delta | delta_pct |
|---|---|---|---|---|---|
| 4000 | 15 | 140.25 | 136.04 | -4.21 | -3.00% |
| 4500 | 20 | 140.25 | 136.04 | -4.21 | -3.00% |
| 3500 | 25 | 127.42 | 123.60 | -3.82 | -3.00% |
| 2750 | 15 | 122.29 | 118.62 | -3.67 | -3.00% |
| 2250 | 10 | 120.50 | 116.89 | -3.61 | -3.00% |
| 2000 | 10 | 119.00 | 115.43 | -3.57 | -3.00% |
| 3500 | 15 | 127.50 | 124.05 | -3.45 | -2.71% |
| 2250 | 5 | 110.90 | 107.58 | -3.33 | -3.00% |
| 2000 | 30 | 109.45 | 106.17 | -3.28 | -3.00% |
| 2000 | 5 | 109.00 | 105.73 | -3.27 | -3.00% |
| 1750 | 20 | 107.50 | 104.28 | -3.22 | -3.00% |
| 5000 | 60 | 107.00 | 110.21 | +3.21 | +3.00% |
| 2750 | 5 | 106.00 | 102.82 | -3.18 | -3.00% |
| 3000 | 10 | 105.69 | 108.86 | +3.17 | +3.00% |
| 3000 | 15 | 110.09 | 113.25 | +3.16 | +2.87% |

## Status

ANNOTATE ONLY. No .pvv emitted. Review the proposal before running
`tools/generate_iter8_patch.py`.