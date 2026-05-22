# iter_8 Patch -- VE smoothing + aggressive WOT spark experiment

Generated: 2026-05-12T23:13:01+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

Base: `iter_6_patched.pvv`, not iter_7. iter_7 (+1 deg WOT spark) was safe
but did not beat iter_6. User requested the smoothed VE tune with +2 deg
where it matters. This file is experimental and must be validated before final use.

- base SHA-256: `fd5ba039839ef3cc2c1608d963f388927c0172c7d843aa38bd04e2ec0bd1a5ff`
- iter_8_patched.pvv SHA-256: `bdcd004fd9d333e6d3d90e39d37c574e4b294a5a02aa9bb1855ebfcc8c50dd21`

## Spark change

- +2.0 deg at MAP=100 kPa columns only
- RPM rows: 4500, 5000, 5500
- Front and rear cylinders
- 5500/95 kPa knock notch preserved
- Spark clamp: +2.0 deg, inside the +/-3.0 deg safety clamp

| cylinder | RPM | MAP | base | new | delta |
|---|---:|---:|---:|---:|---:|
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 4500 | 100 | 32.0 | 34.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| front | 5500 | 100 | 35.0 | 37.0 | +2.0 |
| front | 5500 | 100 | 36.0 | 38.0 | +2.0 |
| front | 5500 | 100 | 36.0 | 38.0 | +2.0 |
| front | 5500 | 100 | 36.0 | 38.0 | +2.0 |
| front | 5500 | 100 | 36.0 | 38.0 | +2.0 |
| front | 5500 | 100 | 36.0 | 38.0 | +2.0 |
| front | 5500 | 100 | 36.0 | 38.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 4500 | 100 | 31.0 | 33.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5000 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5500 | 100 | 33.0 | 35.0 | +2.0 |
| rear | 5500 | 100 | 34.0 | 36.0 | +2.0 |
| rear | 5500 | 100 | 34.0 | 36.0 | +2.0 |
| rear | 5500 | 100 | 34.0 | 36.0 | +2.0 |
| rear | 5500 | 100 | 34.0 | 36.0 | +2.0 |
| rear | 5500 | 100 | 34.0 | 36.0 | +2.0 |
| rear | 5500 | 100 | 34.0 | 36.0 | +2.0 |

## VE smoothing change

- Front VE cells changed: 87
- Rear VE cells changed: 92
- Scope: RPM 1500-5000, TPS 0-60 only
- WOT VE columns (TPS 80/100) untouched
- Per-cell VE delta capped at +/-3%

Top VE changes by absolute delta:

| cylinder | RPM | TPS | base | new | delta | delta_pct |
|---|---:|---:|---:|---:|---:|---:|
| rear | 4000 | 15 | 140.25 | 136.04 | -4.21 | -3.00% |
| rear | 4500 | 20 | 140.25 | 136.04 | -4.21 | -3.00% |
| front | 4500 | 20 | 133.10 | 129.11 | -3.99 | -3.00% |
| front | 4000 | 15 | 130.90 | 126.97 | -3.93 | -3.00% |
| rear | 3500 | 25 | 127.42 | 123.60 | -3.82 | -3.00% |
| rear | 2750 | 15 | 122.29 | 118.62 | -3.67 | -3.00% |
| rear | 2250 | 10 | 120.50 | 116.89 | -3.61 | -3.00% |
| rear | 2000 | 10 | 119.00 | 115.43 | -3.57 | -3.00% |
| front | 2750 | 15 | 116.86 | 113.35 | -3.51 | -3.00% |
| rear | 3500 | 15 | 127.50 | 124.05 | -3.45 | -2.71% |
| front | 2000 | 30 | 111.10 | 107.77 | -3.33 | -3.00% |
| rear | 2250 | 5 | 110.90 | 107.58 | -3.33 | -3.00% |
| rear | 2000 | 30 | 109.45 | 106.17 | -3.28 | -3.00% |
| rear | 2000 | 5 | 109.00 | 105.73 | -3.27 | -3.00% |
| front | 4000 | 25 | 127.63 | 124.40 | -3.24 | -2.54% |
| rear | 1750 | 20 | 107.50 | 104.28 | -3.22 | -3.00% |
| rear | 5000 | 60 | 107.00 | 110.21 | +3.21 | +3.00% |
| rear | 2750 | 5 | 106.00 | 102.82 | -3.18 | -3.00% |
| rear | 3000 | 10 | 105.69 | 108.86 | +3.17 | +3.00% |
| front | 1750 | 20 | 105.50 | 102.33 | -3.17 | -3.00% |

## Tables byte-identical to iter_6

- Engine Displacement (103.0 CID)
- Acceleration Enrichment (iter_6 AE fix preserved)
- AFR / PE AFR
- Deceleration Enleanment
- Max Knock Retard (4 deg cap)
- RPM Limit

## Pull plan

- First pull: 4th gear, watch knock retard live, abort if >4 deg
- If clean: two more 4th-gear WOT pulls
- Judge against iter_6, not iter_7: iter_6 brake-fixed avg = 94.9 hp

## Abort / revert

- Knock retard >4 deg: revert to iter_6
- Audible detonation: revert immediately
- Peak HP below iter_6 again: timing is past MBT, revert to iter_6
- CHT >220 F: abort

Revert file: `iter_6_patched.pvv` (SHA-256 `fd5ba039839ef3cc2c1608d963f388927c0172c7d843aa38bd04e2ec0bd1a5ff`).

---

## Post-flash validation -- 2026-05-12

iter_8 was flashed and tested with pulls `_38`, `_39`, `_40`.

| Pull | Peak HP | Peak RPM | LC2 @ peak | LC2 avg 3-5.5k | Knock | IAT max | CHT max | Rear duty max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| _38 | 93.96 | 5442 | 12.55 | 12.68 | 0.0 | 102F | 142F | 90.9% |
| _39 | 94.28 | 5317 | 12.73 | 12.76 | 0.0 | 106F | 153F | 86.3% |
| _40 | 94.47 | 5514 | 12.92 | 13.04 | 0.0 | 109F | 158F | 85.0% |

Comparison:

| Tune | Pulls | Peak HP avg | Notes |
|---|---|---:|---|
| iter_6 | _31, _32, _33 | 94.91 | Best WOT baseline; 0 knock |
| iter_7 | _35, _36, _37 | 92.99 | +1 deg WOT spark, high IAT, no gain |
| iter_8 | _38, _39, _40 | 94.24 | VE smoothing + +2 deg WOT spark, safe but no clear WOT gain |

Verdict: **safe, but not a WOT power winner.** Knock stayed at zero and temps
were healthy. Since WOT VE was untouched, the VE smoothing can still be useful
for street/cruise feel, but the +2 deg spark sweep did not clearly beat iter_6.

Recommendation: if the priority is final peak dyno number, use `iter_6`. If the
priority is street smoothness and the rider likes the part-throttle feel, iter_8
is acceptable, but it should not be claimed as more powerful than iter_6.
