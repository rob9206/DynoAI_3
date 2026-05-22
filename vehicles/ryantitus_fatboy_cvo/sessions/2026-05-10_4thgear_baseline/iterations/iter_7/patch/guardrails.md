# iter_7 Operational Guardrails

Spark-only revision on top of iter_6. Single dimension change: WOT timing.

## Pull plan

- [ ] Pull 1: gentle 4th-gear WOT to 5500 RPM, watch knock retard channel live
- [ ] Pull 2: full 4th-gear WOT to ~6000 RPM, log
- [ ] Pull 3: confirmation pull (must repeat pull 2 within 1 hp)

## Win conditions

- WOT peak HP: 96+ (target +1-3 hp vs iter_6's 94.9 hp avg)
- WOT LC2 3000-5500: 12.3-12.8 (unchanged vs iter_6)
- Knock retard: 0-2 deg observed; cap is 4 deg
- CHT: <220 F

## Abort criteria (revert to iter_6)

- Knock retard > 4 deg at any RPM
- Peak HP drops below iter_6 baseline
- Audible detonation
- CHT > 220 F

## Known constraints

- Rear injector duty 86-93% in iter_6 -- this iteration does not change fuel,
  duty stays the same. Hardware ceiling unchanged.

See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.