# iter_8 Operational Guardrails

Experimental combined tune: cruise/part-throttle VE smoothing plus +2 deg WOT spark.

## Critical limits

- Abort if knock retard >4 deg
- Abort on any audible detonation
- Abort if CHT >220 F
- Revert if peak HP does not beat iter_6 cleanly

## Pull plan

- Pull 1: 4th gear, watch knock live; stop at ~5500 if anything looks wrong
- Pull 2: full 4th gear to ~6000
- Pull 3: confirmation pull

## Expected behaviour

- WOT AFR should match iter_6 because WOT VE is untouched
- Part-throttle cruise should feel smoother because TPS 0-60 VE spikes are reduced
- Spark is the risk: +2 deg may still be past MBT despite zero knock