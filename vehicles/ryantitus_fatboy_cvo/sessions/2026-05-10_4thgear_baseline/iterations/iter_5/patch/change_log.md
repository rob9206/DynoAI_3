# iter_5 Patch -- combined VE trim + AE fix (supersedes iter_4)

Generated: 2026-05-12T01:09:58+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

iter_3 was flashed and produced two evidence streams:
  1. Five clean 4th-gear pulls: peak HP 91.2-92.0, WOT LC2 11.8-12.4 (rich)
  2. Seven 3rd-gear tip-in pulls (17 events): mid-RPM (3.4k-4.4k) tip-in
     LC2 spiking to 13.9-14.4 (lean)
iter_5 fixes both in one flash. iter_4 (VE trim only) is superseded and
will not be flashed.

- base file: `iter_3_patched.pvv`
- base SHA-256: `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`
- iter_5_patched.pvv SHA-256: `472dda843cea950a24331e3eccf7876a4b4677033627690a836d17bdacefa4d4`
- VE findings: `vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_3\analyses\iter3_dwrt_findings.json`
- VE cells trimmed (front+rear same bins): 30
- VE cells skipped (positive/lean): 40
- VE cells skipped (|delta| < 1.0%): 0
- per-cell VE clamp: +/-5% vs iter_3

## Acceleration Enrichment table

Boost mid-decay AE to address 3000-4700 RPM tip-in lean spikes, and
remove the 0.91 post-event enleanment tail.

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

## Tables changed (3)

- VE (TPS based/Front Cyl): rich WOT cells trimmed only
- VE (TPS based/Rear Cyl): same delta pattern (collector probe)
- Acceleration Enrichment: mid-decay boost + tail enleanment removal

## Tables byte-identical to iter_3

- Engine Displacement (103.0 CID stays)
- Spark Advance Front/Rear (cam advance + 5500 knock notch preserved)
- AFR / PE AFR (targets unchanged)
- Deceleration Enleanment, Max Knock Retard, RPM Limit

## Expected outcome

- WOT 3000-5500 RPM 100% TPS: LC2 moves from ~12.0 toward 12.5-12.8
- 3rd-gear tip-in at 3000-4700 RPM: LC2 max during 0-300ms drops from
  ~14.0 toward 12.5-13.0; tip-in feel crisper
- WOT peak HP: unchanged or +0.5 to +1.5

## Abort criteria post-flash

- WOT LC2 > 13.8 anywhere in 3000-5500 RPM band -- hold, do not flash iter_6
- Tip-in LC2 < 11.0 sustained -- AE overshoot, revert to iter_3
- Knock retard > 4 deg

## Revert

Re-flash `iter_3_patched.pvv` (SHA-256 `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`).
