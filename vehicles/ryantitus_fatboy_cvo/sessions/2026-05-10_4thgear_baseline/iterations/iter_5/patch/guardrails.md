# iter_5 Operational Guardrails

Combined WOT VE trim + Acceleration Enrichment revisions.

## Pull plan (suggested order)

- [ ] First: 3 clean 4th-gear WOT pulls to ~6000 RPM (validate WOT AFR)
- [ ] Second: 5 tip-in events in 3rd gear at ~3500-4500 RPM
      (snap throttle 0% -> 100% in <0.2s)
- [ ] Capture ECU log + DWRT trace for both

## Win conditions

- WOT LC2 in 3000-5500 RPM avg: 12.5 - 13.0 (target 12.8)
- Tip-in LC2 max in first 300 ms: 12.0 - 13.5
- Knock retard: < 2 deg observed; cap is 4 deg

## Abort criteria

- LC2 > 13.8 anywhere at WOT
- LC2 < 11.0 sustained at tip-in (over-enrichment, revert iter_3)
- CHT > 220 F

See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.