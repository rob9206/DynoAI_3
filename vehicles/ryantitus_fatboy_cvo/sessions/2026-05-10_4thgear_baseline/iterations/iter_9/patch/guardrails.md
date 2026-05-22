# iter_9 Operational Guardrails

Decel-only cleanup on top of iter_8. WOT untouched.

## Critical limits

- Stall on tip-out: revert immediately to iter_8
- Lurch on tip-out: revert to iter_8
- WOT HP drop vs iter_8: revert (should never happen)

## Pull plan

- 1st: 4th-gear cruise at light throttle 2500-3500 RPM, log
- 2nd: snap-closed throttle from 4000+ RPM (decel test)
- 3rd: confirmation WOT pull (verify WOT HP matches iter_8)

## Expected behaviour

- Cruise AFR unchanged
- Decel AFR: LC2 should rise from ~12.5 toward ~13.5-14.0 on overrun
- Less decel pop
- WOT identical to iter_8