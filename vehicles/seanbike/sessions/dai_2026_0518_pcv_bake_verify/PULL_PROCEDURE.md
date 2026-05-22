# Seanbike Dyno Session Procedure

Session: `dai_2026_0518_pcv_bake_verify`  
Vehicle: `seanbike` (`1HD1GXM12FC325637`)  
Base tune: `base_tune/base.pvv` (SHA-256 `994f314708dee1d1f7616b8196058e330efbd6ef7e538963d7f328bf6d7b9310`)

## Pre-pull Safety Checks

1. Confirm PCV is physically disconnected from injector harness.
2. Confirm ECU flash readback/cal ID corresponds to the intended baked tune.
3. Cold start and idle for 3 minutes. Abort if any active DTC appears.
4. Verify battery support charger is connected before all loaded pulls.
5. Install wideband in tailpipe collector and log on DynoWare AFR channel.

## Pull Sequence

1. **Shakedown pull** (light load, 2nd or 3rd gear): 2000 to 4000 rpm, part-throttle only.
2. Review AFR and knock trend.
3. **Diagnostic pull** (loaded 4th gear): 2500 rpm to redline.
4. Review AFR, power curve smoothness, and any spark/knock anomalies.

## Abort Criteria (engine off and stop session)

- AFR leaner than `13.7` above 50% TPS.
- Rapidly increasing knock count or audible knock/misfire.
- Sharp head-temp rise or any behavior suggesting detonation.
- Any critical ECU/engine DTC triggered during pull.

## File Drop Workflow

After each pull, copy DynoWare artifacts to:

`C:\CommmandCenter\Customer_Files\seanbike\dyno_inbox`

Expected files:

- DynoWare `.txt` logs
- WinPEP8 `.wp8` files
- Any supporting Power Vision CSV exports

Then verify they appear under:

`vehicles/seanbike/sessions/dai_2026_0518_pcv_bake_verify/iterations/iter_0/pulls/`

and ensure `pulls/manifest.json` has a matching entry for each new file.
