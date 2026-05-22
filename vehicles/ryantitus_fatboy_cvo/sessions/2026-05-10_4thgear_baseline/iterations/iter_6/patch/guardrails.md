# iter_6 Operational Guardrails

AE-only revision on top of iter_3. Single change: tip-in fueling.

## Pull plan

- [ ] First: 3 clean 4th-gear WOT pulls to 6000+ RPM (must match iter_3 envelope:
      reach ~5800 RPM at ~115 mph in gear ratio ~51)
- [ ] Second: 5 tip-in events in 3rd gear at 3000-4500 RPM
      (snap throttle 0% -> 100% in <0.2s)

## Win conditions

- WOT peak HP: 91-92 (matches iter_3 baseline)
- WOT LC2 3000-5500 RPM avg: ~11.5-11.7 (richer is fine, this bike likes it)
- Tip-in LC2 max in first 300 ms: 12.0 - 13.5 (improvement vs iter_3)
- Knock retard: < 2 deg observed; cap is 4 deg

## Abort criteria

- LC2 < 11.0 sustained at tip-in (AE over-enriched, revert iter_3)
- Knock retard > 4 deg
- CHT > 220 F
- WOT HP drops vs iter_3 baseline (something is wrong)

## Known constraints

- Rear injector duty was 95-105% above 5500 RPM in prior data; expect
  similar in iter_6. This is a hardware ceiling, not a tune issue.

See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.