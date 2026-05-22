# iter_3 Operational Guardrails

Same dyno-operator rules as iter_2; VE was adjusted from tailpipe LC2.

## LC2 sanity

- [ ] LC2 reads a plausible AFR band (roughly 10-19) before loading the drum
- [ ] First 10 s of pull 1: LC2 must move with mixture; stuck 22.39 = dead probe

## After iter_3 flash

- [ ] Compare LC2 to Desired AFR / PE targets; >1.5 AFR systematic error in a
      RPM/TPS zone flags a bad bin or transient data -- schedule iter_4

See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.