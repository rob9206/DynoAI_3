# Tier 5 — Real-rig smoke test

End-to-end validation against actual hardware: DynoWare RT-150 + Power Core
+ a real bike on the dyno. This is the only thing left that the
PC-based test sweep can't cover.

**Scope of this checklist:** validate the workspace flow and the LC-2
canonicalization fix on a single bike under controlled conditions. **Do
not** run any tune that hasn't been reviewed before flashing. **Do not**
flash any tune that the corrections file flags as "extreme" (>±25%).

---

## Pre-arrival prep (do these on this PC before driving to the rig)

### P-1. Branch / PR state

The fixes from `fix/test-followups-from-tier2` should be merged into
`main` before this test, so the rig is exercising final code:

- [ ] `git checkout main && git pull` shows the latest tip includes
  commits `a462361` (or whatever ID `fix/test-followups-from-tier2`
  squashed to). If not, merge the PR first.

### P-2. Snapshot / rollback plan

Before driving anything onto a real ECM, you need a verified rollback path.

- [ ] Confirm the bike's **current flashed PVV** is on a USB stick AND
  also archived on the laptop you'll bring. This is your "known good"
  if anything goes wrong.
- [ ] Note the bike's calibration part number (CalPN) so you can verify
  the PVV identity after the test. The workspace records
  `base_tune_sha256` for this purpose.
- [ ] If the bike has any datalogging history that matters, copy the
  Power Core `Documents/Power Core` and `Documents/Power Vision`
  trees to a backup location.

### P-3. Network / multicast plan

JetDrive runs on UDP multicast `224.0.2.10:22344`. Some shop networks
block multicast at the AP/switch.

- [ ] Confirm the laptop and the DynoWare RT-150 will be on the same
  Layer-2 subnet (no router hop between them).
- [ ] On the laptop: `Get-NetAdapter | Where-Object Status -eq Up` to
  identify the primary NIC. Note its IP address.
- [ ] If the laptop has WiFi + ethernet both connected, set
  `JETDRIVE_IFACE=<NIC IP>` so multicast joins on the right interface.
  Otherwise discovery binds to whichever Windows decides, which is
  usually wrong.

### P-4. LC-2 calibration

The `wideband_rescale.py` defaults are `0V=7.35 AFR, 5V=22.39 AFR`
(petrol stoich). This is correct **only** if your LC-2 is configured for
its default analog output mapping. If a tuner has previously
re-flashed the LC-2 with a custom min/max:

- [ ] Open Innovate LM Programmer, connect the LC-2, read its analog
  configuration. Note `V_MIN`, `V_MAX`, `AFR_MIN`, `AFR_MAX`.
- [ ] If they don't match `0/5/7.35/22.39`, set environment overrides
  before starting the API:

  ```powershell
  $env:DYNOAI_WIDEBAND_V_MIN = "<your V_MIN>"
  $env:DYNOAI_WIDEBAND_V_MAX = "<your V_MAX>"
  $env:DYNOAI_WIDEBAND_AFR_MIN = "<your AFR_MIN>"
  $env:DYNOAI_WIDEBAND_AFR_MAX = "<your AFR_MAX>"
  ```
- [ ] Run a quick sanity check: server log on startup should print the
  active calibration. `python -c "from api.services.jetdrive.wideband_rescale import get_active_calibration; print(get_active_calibration())"`

### P-5. Workspace root

- [ ] Decide where workspace data should live on the rig laptop. Default
  is `vehicles/` next to the working directory. For a real shop, set
  `DYNOAI_WORKSPACE_ROOT=D:\DynoAI\vehicles` or wherever your
  long-term storage is. Don't leave it in a temp directory.
- [ ] If you'll watch a Power Core export folder for auto-import, also
  decide if you want the workspace `WorkspaceWatcher` enabled per
  vehicle (set on vehicle profile via PATCH `watch_folder`) — you can
  defer this; it's an opt-in convenience, not part of the smoke test.

### P-6. Frontend build (if running production-style)

If you're going to use the React app at the rig:

- [ ] `cd frontend && npm install && npm run build` produces `dist/`.
- [ ] Configure your reverse proxy or run the API with
  `--with-static-frontend` if you have that option, OR run vite dev
  server `npm run dev` with `VITE_API_URL` pointed at the API
  process. The latter is fine for a smoke test.

---

## At the rig

### A. Pre-flight (no engine running, key off, dyno arms inserted)

- [ ] DynoWare RT-150 powered on, ethernet to laptop (or to shared switch).
- [ ] Power Core launched. Confirm Power Core sees the dyno and live
  channels appear in its scope. If they don't show in Power Core,
  fix that before continuing — the issue is upstream of DynoAI.
- [ ] Start DynoAI API:

  ```powershell
  cd C:\Dev\DynoAI_3
  $env:DYNOAI_WORKSPACE_ROOT = "D:\DynoAI\vehicles"
  $env:JETDRIVE_IFACE = "<laptop NIC IP>"
  python -m flask --app api.app run --host 0.0.0.0 --port 5001 --no-reload
  ```

  Watch for:
  - `[+] Tuning Workspace registered at /api/workspace`
  - `[+] Power Core watch-folder API registered at /api/powercore/watch`
  - `* Running on http://0.0.0.0:5001`

- [ ] In another terminal, sanity-check discovery:

  ```powershell
  curl http://localhost:5001/api/jetdrive/hardware/discover?timeout=5
  ```

  Expect `providers_found >= 1` with the DynoWare RT-150 at its known
  IP and >= 30 channels listed.

### B. Workspace setup

- [ ] Create the vehicle for the bike under test:

  ```powershell
  $body = @{ name = "Test Bike Apr 27"; year = 2017; make = "Harley"; model = "FXDLS"; displacement_ci = 107 } | ConvertTo-Json
  curl -X POST http://localhost:5001/api/workspace/vehicles -H "Content-Type: application/json" -d $body
  ```

  Note the returned `id` (slugified).

- [ ] Create a session under that vehicle:

  ```powershell
  curl -X POST http://localhost:5001/api/workspace/vehicles/<id>/sessions -H "Content-Type: application/json" -d "{}"
  ```

  Note the session `id` (timestamp). Confirm `active_iteration_id == "iter_0"`.

- [ ] Upload the bike's current flashed PVV (the same one you noted in P-2):

  ```powershell
  curl -X POST http://localhost:5001/api/workspace/vehicles/<vid>/sessions/<sid>/upload -F "files=@C:\path\to\current_tune.pvv"
  ```

  Verify response shows `routed[0].slot == "base_tune"` and
  `type == "pvv"`.

- [ ] Hit the status endpoint and screenshot the checklist:

  ```powershell
  curl http://localhost:5001/api/workspace/vehicles/<vid>/sessions/<sid>/status
  ```

  Expect `has_vehicle: true`, `has_base_tune: true`, `pull_count: 0`,
  `ready_to_analyze: false` (no pulls yet).

### C. Live capture validation (the LC-2 canonicalization test)

This is the heart of why we did the merge — proving the volts -> AFR
rescale happens server-side before any consumer sees the value.

- [ ] Start live capture:

  ```powershell
  curl -X POST http://localhost:5001/api/jetdrive/hardware/start
  ```

- [ ] Wait 5 seconds. Read live channels:

  ```powershell
  curl http://localhost:5001/api/jetdrive/hardware/live/data
  ```

- [ ] In the response JSON, look for the AFR slots. You should see
  **either** `"AFR Front"` and `"AFR Rear"` (canonicalized),
  **OR** the original `"Air/Fuel Ratio 1/2"` channel names if the
  rig is running widebands directly (not via LC-2 voltage).

  **CRITICAL:** if you see a channel like `"LC2 Volts Petrol AFR1"`
  with a value in the range 0-5, the rescale didn't fire. Possible causes:
  - LC-2 calibration override missing (P-4 wasn't done correctly).
  - The DynoWare channel name doesn't match the matcher
    (`volts` + `petrol` + `afr` all required, case-insensitive).
    If your shop's Power Core renamed the channel, the matcher won't
    catch it. Server-side fix: extend `match_wideband_channel()` in
    `api/services/jetdrive/wideband_rescale.py`.

- [ ] Idle the engine for 60 seconds. Confirm AFR readings stay in
  the 13-15 range (warm closed-loop), not 0-5.

- [ ] Take three screenshots of `/hardware/live/data` at idle, low cruise,
  and full off-throttle. Save them to the rig's documentation folder.

### D. Pull capture and routing

- [ ] Run a single 4th-gear sweep (or whatever your standard is for the
  bike under test).
- [ ] Stop live capture: `curl -X POST http://localhost:5001/api/jetdrive/hardware/stop`
- [ ] Power Core will write a CSV/WP8 to its export folder. Confirm
  the file landed.
- [ ] Upload it to the workspace:

  ```powershell
  curl -X POST http://localhost:5001/api/workspace/vehicles/<vid>/sessions/<sid>/upload -F "files=@C:\path\to\pull.csv"
  ```

  Verify `routed[0].slot == "pulls"` and `type == "powervision_csv"` (or
  `"wp8"` / `"dynojet_txt"` depending on what Power Core produced).

- [ ] Status check should now show `pull_count >= 1`,
  `has_afr_data: true` (if the pull is TXT or CSV with AFR columns),
  `ready_to_analyze: true`.

### E. Analyze and review

- [ ] Run analysis:

  ```powershell
  curl -X POST http://localhost:5001/api/workspace/vehicles/<vid>/sessions/<sid>/analyze -H "Content-Type: application/json" -d "{}"
  ```

- [ ] In the response, sanity-check:
  - `success: true`
  - `errors: []`
  - `data_source` matches what you uploaded
  - `afr_mean_error_pct` is small (usually 0-10% on a stock-ish bike)
  - `zones_adjusted` is plausible (typically 5-50 zones for a single pull)
  - `peak_hp` is plausible for the bike (e.g., 60-120 hp for a stock M8)
  - `correction_pvv_path` and `analysis_json_path` are populated
  - `peak_hp_rpm` is null (Dynojet TXT can't fill it) but `peak_hp_mph` IS
    populated -- this is the units-not-conflated fix from
    `fix/test-followups-from-tier2`

- [ ] Open the persisted `autotune_<ts>.json` from the iteration's
  `analyses/` folder. Confirm `success` field matches the API response
  and `analysis_json_path` self-references the correct file. (This is
  the persistence-consistency fix from the same PR.)

- [ ] Open the correction PVV in Power Core's TuneLab. Verify it's a
  valid PVV (no XML errors). Read out the correction percentages.

  **STOP CRITERIA:** if any cell shows correction > +25% or < -25%, do
  NOT flash. Investigate why. Common causes: AFR plausibility issue,
  wrong base tune uploaded, wrong target AFR for this engine.

### F. Apply and re-validate (optional, only if E was clean)

This is the actual "does it work" test, not just "does it run."

- [ ] In Power Core, apply the correction PVV onto the base tune. Save
  as a new revision. **Do not flash yet** — review the resulting tune
  table by table.
- [ ] If you trust the result: flash. Note the time, exact CalPN
  written, and any post-flash diagnostics from the ECM.
- [ ] Run a second pull on the bike (same gear, same conditions).
- [ ] Upload the new pull to a new iteration:

  ```powershell
  curl -X POST http://localhost:5001/api/workspace/vehicles/<vid>/sessions/<sid>/iterations -H "Content-Type: application/json" -d "{}"
  ```

  Then upload the new pull to the new iteration.

- [ ] Run analyze on the new iteration. Compare:
  - Did `afr_mean_error_pct` drop versus the first iteration?
  - Did `zones_adjusted` shrink (corrections converging)?
  - Are there any new "extreme" cells that didn't exist before?

  Convergence between iterations is the gold standard that the system
  is producing real, useful corrections.

---

## What to send back when done

Whether the test passes, partially passes, or fails, capture:

- [ ] `vehicles/<vid>/` directory tree (zip + send).
- [ ] All three live-data snapshots from step C.
- [ ] The per-iteration analyze API responses.
- [ ] Power Core screenshots of the imported correction PVV.
- [ ] If anything looked wrong, the API server log (stdout from the
  Flask process during the session).

If `peak_hp` looked off, also send the raw pull file and the analysis
JSON; the Dynojet TXT parser's column inference may need to be
extended for that specific pull's column shape.

---

## Things that **should NOT** happen

If any of these occur, stop the test and document:

1. AFR values in the 0-5 range on a channel labelled `AFR Front` /
   `AFR Rear`. Means the rescale didn't fire.
2. `zones_adjusted` = 0 with `afr_mean_error_pct` > 5%. Means the
   binning or the base-tune import failed silently.
3. `correction_pvv_path` populated but the file is 0 bytes or invalid
   XML.
4. `success: false` on the API response with `correction_pvv_path`
   non-null. Internal inconsistency.
5. Live capture starts but `pull_count` doesn't increase after a real
   pull. Means the watch path isn't seeing what Power Core wrote.

Each of these is a follow-up issue worth filing.
