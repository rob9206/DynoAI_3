# iter_2 Operational Guardrails

Enforced at the dyno; not encoded in the .pvv. Mirrored in
`vehicles/ryantitus_fatboy_cvo/profile.json` under `tuning_guardrails`.

## Pre-pull checklist

- [ ] CHT start temperature less than 220 F
- [ ] At least 60 seconds since previous WOT pull
- [ ] Dyno tailpipe wideband warm and reading sane (no on-bike sensor)
- [ ] iter_2_patched.pvv flashed; SHA-256 matches change_log.md
- [ ] Knock retard cap is now 4 deg, not 8 -- watch the live retard channel
- [ ] First 2-3 pulls are diagnostic baselines; expect the engine to feel
      slightly richer than the Dynojet stage (16.4 percent more fuel command)

## Analysis ceiling

Treat any data above 5500 RPM as informational only. Observed peak
HP was ~5300 RPM. Rev limiter is back at 6200 (OEM). The 5500-6200
range is past the powerband and noisy without AFR feedback.

## AFR ground truth

There are NO O2 sensors on this bike or in the exhaust. AFR validation
must come from the dyno's tailpipe wideband (DynoWare RT). No on-bike
sensor will ever produce AFR for this vehicle.

## What unlocks iter_3

- Dyno tailpipe wideband connected and producing valid 10.0-19.0 readings
- 2-3 clean WOT pulls captured with AFR present
- iter_2 patch verified safe (no rich rear, no recurring knock)

## Generated values (for tooling)

| key                                  | value |
| ------------------------------------ | ----- |
| `abort_if_cht_above_f`               | 220.0 |
| `min_cool_down_s_between_wot_pulls`  | 60    |
| `wot_rpm_ceiling_for_analysis`       | 5500  |
| `max_knock_retard_deg` (in tune)     | 4.0   |
| `no_o2_sensors_on_bike`              | true  |
| `afr_source`                         | `dyno_tailpipe_wideband_only` |