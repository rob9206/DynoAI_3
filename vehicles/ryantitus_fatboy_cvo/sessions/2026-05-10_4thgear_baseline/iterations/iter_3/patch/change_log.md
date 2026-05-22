# iter_3 Patch -- supersedes iter_2 v3 (single flash)

Generated: 2026-05-12T00:08:42+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

iter_2 v3 was generated but never flashed. Dyno pulls on the original
Dynojet stage tune were captured with Innovate venturi wideband on
DynoWare RT LC2. iter_3 applies every iter_2 v3 change plus VE corrections
from LC2 vs Dynojet AFR target tables (AFR targets left unchanged).

- base file: `dynojet_stage.pvv`
- base SHA-256: `9bd9801281b87933f530a8bdcd0a4c7551e29eb60b7caa1c894fc57e20e53dad`
- iter_3_patched.pvv SHA-256: `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`
- findings: `vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_2\analyses\iter2_dwrt_findings.json`
- VE cells adjusted (front+rear same bins): 70

## Evidence (DWRT logs)
- `6th gear load then wot.txt` SHA-256 `3e1796fababdf4a25d9befb79e2285982e18f54cdc27aa904a043e867008dbd5`
- `6th gear load then wot_0.txt` SHA-256 `8ff6ce2bc3cf5de9f9b610a2aec43061a831b4cb9634750debc299dab952cdb4`
- `6th gear load then wot_1.txt` SHA-256 `0c54400d89b180da85026b412b0d816ab19d6e3ce4e27459964970923a1fabdb`
- `6th gear load then wot_2.txt` SHA-256 `57d10645a658fea84952b083427a38f058b0de58f49dbf42c69b34dc23db7990`
- `6th gear load then wot_3.txt` SHA-256 `a0564d97f5170561ea1ef431224d4cc532ed5ea968af689aa766bcd2b8738c3a`
- `6th gear load then wot_4.txt` SHA-256 `aa9d1c4bb5ea5679d80a2abe023798a5772580a202d33c8303f6b09d7ef6e0c3`
- `6th gear load then wot_5.txt` SHA-256 `c9a1515144cfe3f952bdc7e5b145b1d94c508093c19a897c5b2858fd52785c42`
- `6th gear load then wot_6.txt` SHA-256 `fe0fd5f1a702d84518e5e4c23b029db3f6e7d4aac5579729d119a74b2ad5accb`
- `6th gear load then wot_7.txt` SHA-256 `c91e966bf5edf9048d7f5922c95a75e393cace155a032a2f00f6238623df8948`
- `6th gear load then wot_9.txt` SHA-256 `98de77f0aa42f72b1149d9242784de231f413819fba4a600f6f15099f6653169`
- `PV_Logfile_5.csv_18.txt` SHA-256 `31b6988b39aedc3f8dd0d0af2ad3d7ce7724fd9a980064eb49f9d3cc7ca428f7`
- `PV_Logfile_5.csv_19.txt` SHA-256 `2c9c0d5d7dd76fce0b4702152ff79ca784cc5516bf07eca02751942cb3c2bd9b`

## iter_2 v3 changes (included)

- Engine Displacement: 88.48 -> 103.00 CID
- Spark front/rear cells changed: 40 / 40
- Deceleration Enleanment: all -> 1.0
- Max Knock Retard: cap 4 deg
- RPM Limit: -> 6.2 RPMx1000

## iter_3 additions

- VE (TPS based/Front Cyl) and VE (TPS based/Rear Cyl): same bulk-AFR
  correction applied to both (collector probe; no per-cylinder split).
- Per-cell VE change capped at +/-10% vs Dynojet stage.

## LC2 probe health (annotate-only)

Rows where LC2 pegged at the A/D ceiling were excluded from the median
binning but remain in the raw logs. After flash, watch LC2 in the first
10 s of pull 1; a stuck rail voltage means replace the probe before trusting VE.

## First-pull post-flash protocol

Same abort criteria as iter_2 v3 (injector duty, knock peg, CHT, smoke).
Additionally: if LC2 flatlines or pegs at ceiling, abort and replace probe.

## Revert

Re-flash `dynojet_stage.pvv` (SHA-256 `9bd9801281b87933f530a8bdcd0a4c7551e29eb60b7caa1c894fc57e20e53dad`).
