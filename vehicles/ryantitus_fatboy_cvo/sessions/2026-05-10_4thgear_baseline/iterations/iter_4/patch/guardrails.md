# iter_4 Operational Guardrails

Small lean trim on rich cells from iter_3 post-flash evidence.

## Before pulls

- [ ] LC2 reads plausible band (10-19) before loading drum
- [ ] DynoWare RT RPM source still 'Harley - ECU Engine Speed' / channel stable
- [ ] CHT < 220F before pull

## During pulls

- [ ] LC2 between 12.5 and 13.5 at WOT 3000-5500 RPM is the win condition
- [ ] LC2 > 13.8 anywhere at WOT -- abort, do not flash iter_5
- [ ] Knock retard > 4 deg -- abort and report

## After pulls

- [ ] Capture 3 clean 4th-gear WOT pulls minimum
- [ ] Compare peak HP and AFR distribution to iter_3 5-pull set

See `vehicles/ryantitus_fatboy_cvo/profile.json` tuning_guardrails.