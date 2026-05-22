# iter_7 Patch -- targeted +1 deg WOT spark sweep on top of iter_6

Generated: 2026-05-12T22:54:26+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

iter_6 was flashed and validated on 2026-05-12. Brake-fixed pulls _31..33 made
94.5 / 95.1 / 95.2 hp peak with **0 deg knock retard** in the entire pull and
rear injector duty 86-93%. The bike has unused knock margin and is at the
injector ceiling -- spark advance is the only remaining HP lever without a
hardware change.

iter_7 adds +1 deg ONLY at the WOT MAP columns (MAP = 100 kPa) at peak-power
RPMs (4500, 5000, 5500). Both cylinders. The iter_2 knock notch at
5500 / 95 kPa is left untouched (we are sweeping a column to the right of it).

- base file: `iter_6_patched.pvv`
- base SHA-256: `fd5ba039839ef3cc2c1608d963f388927c0172c7d843aa38bd04e2ec0bd1a5ff`
- iter_7_patched.pvv SHA-256: `8f9c3eb6b0cf7f2fe82e189e165d80d35fd3743a6cfab8703c99c8fd7b7372ea`

## Spark cells changed (Front + Rear)

### Front Cyl

| RPM | MAP | base | new | delta |
|---|---|---|---|---|
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 4500 | 100 | 32.0 | 33.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5500 | 100 | 35.0 | 36.0 | +1.0 |
| 5500 | 100 | 36.0 | 37.0 | +1.0 |
| 5500 | 100 | 36.0 | 37.0 | +1.0 |
| 5500 | 100 | 36.0 | 37.0 | +1.0 |
| 5500 | 100 | 36.0 | 37.0 | +1.0 |
| 5500 | 100 | 36.0 | 37.0 | +1.0 |
| 5500 | 100 | 36.0 | 37.0 | +1.0 |

### Rear Cyl

| RPM | MAP | base | new | delta |
|---|---|---|---|---|
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 4500 | 100 | 31.0 | 32.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5000 | 100 | 33.0 | 34.0 | +1.0 |
| 5500 | 100 | 33.0 | 34.0 | +1.0 |
| 5500 | 100 | 34.0 | 35.0 | +1.0 |
| 5500 | 100 | 34.0 | 35.0 | +1.0 |
| 5500 | 100 | 34.0 | 35.0 | +1.0 |
| 5500 | 100 | 34.0 | 35.0 | +1.0 |
| 5500 | 100 | 34.0 | 35.0 | +1.0 |
| 5500 | 100 | 34.0 | 35.0 | +1.0 |

## Tables byte-identical to iter_6

- VE (TPS based/Front Cyl), VE (TPS based/Rear Cyl)
- Engine Displacement (103.0 CID)
- Acceleration Enrichment (iter_6 AE fix preserved)
- AFR / PE AFR, Deceleration Enleanment, Max Knock Retard (4 deg cap), RPM Limit

## Expected outcome (4th-gear pulls)

- Peak HP: 96-98 (+1-3 hp over iter_6's 94.9 hp average)
- WOT LC2 in 3000-5500 RPM: ~12.3-12.8 (unchanged from iter_6; pure spark change)
- Knock retard: 0-2 deg target; abort if knock > 4 deg or any cell hits the cap
- Rear injector duty: ~86-93% (unchanged; this is hardware-limited)

## Abort criteria post-flash

- Knock retard > 4 deg sustained at any RPM -- back off, revert to iter_6
- Peak HP drops vs iter_6 -- spark is past MBT, revert
- Detonation audible -- revert immediately
- CHT > 220 F at WOT

## Pull plan

- Pull 1: gentle WOT in 4th, watch knock retard live
- Pull 2: full WOT in 4th, log to redline
- Pull 3: confirm pull 2 (repeatability)

## Revert

Re-flash `iter_6_patched.pvv` (SHA-256 `fd5ba039839ef3cc2c1608d963f388927c0172c7d843aa38bd04e2ec0bd1a5ff`).
