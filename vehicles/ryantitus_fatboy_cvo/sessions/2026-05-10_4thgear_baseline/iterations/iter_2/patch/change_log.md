# iter_2 Patch -- Dynojet Stage Base, Displacement Fix, Safety Touches

Generated: 2026-05-11T23:17:04+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

- base file: `dynojet_stage.pvv`
- base SHA-256: `9bd9801281b87933f530a8bdcd0a4c7551e29eb60b7caa1c894fc57e20e53dad`
- iter_2_patched.pvv SHA-256: `fb1ceb0ee5ae83040a8c136aa73123ac761824a67d84fbb3b5d904efec4cf4a1`

## Context

iter_1 ran on the Dynojet stage tune which has Engine Displacement
incorrectly set to 88.48 CID (almost certainly a wrong-template error;
the bike is actually 103 CID). The stage tune compensated by slashing
VE tables and richening AFR targets. This patch fixes the root cause.

## Changes (six tables)

### 1. Engine Displacement

- base: 88.48 CID
- new:  103.00 CID
- engine fuel command delta: +16.4 percent everywhere

This is the single largest fueling change in this session. iter_1 max
injector duty was 71 percent, so this puts duty around 83 percent worst
case -- inside safe headroom, but tight. First pulls post-flash are
diagnostic, not performance runs.

### 2. Spark Advance (Front + Rear)

- cells changed (front / rear): 40 / 40
- cam-driven advance: +1.0 deg in 2000-4000 RPM x 60-95 kPa
- knock notch: -2.0 deg at (5500 RPM, 95 kPa),
  -1.0 deg at 4 adjacent cells
- knock notch overrides cam advance in any overlapping cell
- clamp: +/-3 deg per cell from base

### 3. Deceleration Enleanment

- base range: 0.34 to 0.80
- new: 1.00 (all 12 CHT cells)

Eliminates fuel cut on overrun. Cures exhaust popping on V&H true duals.

### 4. Max Knock Retard vs RPM

- base: 8 deg across all 12 RPM cols
- new:  4 deg (capped)

Lower cap means knock surfaces in logs sooner instead of being masked.

### 5. RPM Limit

- base: 5.6 RPMx1000 (Dynojet stage pulled 600 RPM)
- new:  6.2 RPMx1000 (OEM ceiling restored)

Our analysis ceiling (vehicle profile guardrail) stays at 5500 RPM.

## Tables NOT modified (byte-identical to base)

These would require dyno tailpipe wideband AFR to change safely:
- PE Air-Fuel Ratio (WOT AFR target)
- Air-Fuel Ratio (idle/cruise AFR target)
- VE (TPS based/Front Cyl)
- VE (TPS based/Rear Cyl)

These are identity/safety items the Dynojet stage owns:
- Calibration ID (touching this breaks the flash)
- Speedometer Calibration
- Acceleration Enrichment (Dynojet's +50-100 percent tip-in)
- Spark Adjust By Engine Temp (Dynojet's heat-soak retard)

## No O2 sensors on bike or in exhaust

AFR validation in iter_3 and beyond must come from the dyno's tailpipe
wideband sniffer (DynoWare RT). There is no on-bike sensor to read.

## First-pull post-flash protocol

Treat the first 2-3 pulls after flash as diagnostic baselines.
Abort criteria:

- Injector duty rear > 90 percent at any point
- Knock retard pegged at the new 4 deg cap for > 0.2 s sustained
- CHT > 220 F at pull start
- Visible black smoke or strong fuel smell at idle

## Revert procedure

Re-flash `dynojet_stage.pvv` (SHA-256 `9bd9801281b87933f530a8bdcd0a4c7551e29eb60b7caa1c894fc57e20e53dad`) to restore the
tune that was on the bike before iter_2.
