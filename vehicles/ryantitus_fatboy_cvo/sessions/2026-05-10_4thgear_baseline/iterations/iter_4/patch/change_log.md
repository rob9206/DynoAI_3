# iter_4 Patch -- small lean trim on top of iter_3

Generated: 2026-05-12T00:31:42+00:00
Vehicle: Ryan Titus 2006 Fat Boy CVO (103 ci)
Session: 2026-05-10_4thgear_baseline

iter_3 was flashed and produced 5 clean 4th-gear pulls in the 91.2-92.0 hp
band with LC2 peak AFR of 11.8-12.4 (rich of Dynojet PE target ~12.8 by
0.4-1.0 AFR). iter_4 walks back the over-fueling at WOT cells with strong
evidence. Only NEGATIVE (rich-cell) VE corrections are applied; positive
(lean) corrections are skipped this iteration because the high-error
light-TPS cells have low sample counts and likely contain transient noise.

- base file: `iter_3_patched.pvv`
- base SHA-256: `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`
- iter_4_patched.pvv SHA-256: `2a16ec98ae98d7546fb72d98ffa21ef7b1aa72a600d2ffbbf001a26882947cd5`
- findings: `vehicles\ryantitus_fatboy_cvo\sessions\2026-05-10_4thgear_baseline\iterations\iter_3\analyses\iter3_dwrt_findings.json`
- VE cells trimmed (front+rear same bins): 30
- VE cells skipped (positive/lean, this iter): 40
- VE cells skipped (|delta| < 1.0%): 0
- per-cell clamp: +/-5% vs iter_3

## Tables changed vs iter_3 (base)

- VE (TPS based/Front Cyl): rich cells trimmed only
- VE (TPS based/Rear Cyl): same delta pattern (collector probe, no per-cyl split)

## Tables byte-identical to iter_3

- Engine Displacement (103.0 CID stays)
- Spark Advance Front/Rear (cam advance + 5500 knock notch preserved)
- AFR / PE AFR (targets unchanged -- ground truth is still Dynojet PE)
- Deceleration Enleanment, Max Knock Retard, RPM Limit

## Evidence (DWRT logs from iter_3 post-flash)
- `6th gear load then wot.txt` SHA-256 `3e1796fababdf4a25d9befb79e2285982e18f54cdc27aa904a043e867008dbd5`  peak_hp=94.387
- `6th gear load then wot_0.txt` SHA-256 `8ff6ce2bc3cf5de9f9b610a2aec43061a831b4cb9634750debc299dab952cdb4`  peak_hp=89.323
- `6th gear load then wot_1.txt` SHA-256 `0c54400d89b180da85026b412b0d816ab19d6e3ce4e27459964970923a1fabdb`  peak_hp=90.249
- `6th gear load then wot_2.txt` SHA-256 `57d10645a658fea84952b083427a38f058b0de58f49dbf42c69b34dc23db7990`  peak_hp=-32.262
- `6th gear load then wot_3.txt` SHA-256 `a0564d97f5170561ea1ef431224d4cc532ed5ea968af689aa766bcd2b8738c3a`  peak_hp=92.6
- `6th gear load then wot_4.txt` SHA-256 `aa9d1c4bb5ea5679d80a2abe023798a5772580a202d33c8303f6b09d7ef6e0c3`  peak_hp=91.164
- `6th gear load then wot_5.txt` SHA-256 `c9a1515144cfe3f952bdc7e5b145b1d94c508093c19a897c5b2858fd52785c42`  peak_hp=91.987
- `6th gear load then wot_6.txt` SHA-256 `fe0fd5f1a702d84518e5e4c23b029db3f6e7d4aac5579729d119a74b2ad5accb`  peak_hp=91.52
- `6th gear load then wot_7.txt` SHA-256 `c91e966bf5edf9048d7f5922c95a75e393cace155a032a2f00f6238623df8948`  peak_hp=91.677
- `6th gear load then wot_9.txt` SHA-256 `98de77f0aa42f72b1149d9242784de231f413819fba4a600f6f15099f6653169`  peak_hp=91.423
- `PV_Logfile_5.csv_18.txt` SHA-256 `31b6988b39aedc3f8dd0d0af2ad3d7ce7724fd9a980064eb49f9d3cc7ca428f7`  peak_hp=68.599
- `PV_Logfile_5.csv_19.txt` SHA-256 `2c9c0d5d7dd76fce0b4702152ff79ca784cc5516bf07eca02751942cb3c2bd9b`  peak_hp=75.423

## Expected outcome

- Peak LC2 AFR moves from ~12.0 toward ~12.5-12.8 at WOT 3000-5500 RPM
- Peak HP: same or +0.5 to +1.5 (MBT shift from rich to near-target)
- If HP drops or LC2 goes above 13.5 in any 100% TPS cell, hold and review

## First-pull post-flash protocol

- 4th gear, same dyno setup as iter_3
- Watch LC2 in 3000-5500 RPM 100% TPS window; expect 12.5-12.8
- Abort if LC2 > 13.8 (too lean of MBT, risk of knock)
- Abort if knock retard > 4 deg (cap from iter_3)

## Revert

Re-flash `iter_3_patched.pvv` (SHA-256 `2be2e8520c73f66e47eb611aeeddc1a5e0139a597c938a855c77b3ed485370dd`).
