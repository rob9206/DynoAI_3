
FXDLS Wheelie VE Logging Template — Instructions

Purpose:
This CSV is for logging Target Tune (or wideband trim) data in % correction.
It matches the AFR/Spark table bins used in your Wheelie v1.0 tune.

How to use:
1. After a ride with Target Tune (closed-loop learning enabled), export the trim data (short-term or long-term fuel trims).
2. Average the trims into these RPM/MAP bins:
   - RPM: 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500
   - MAP: 35, 50, 65, 80, 95 kPa
3. Enter values as % (e.g., +5 = system added 5% fuel, so VE table is too low).
4. Upload the filled CSV back here. I’ll process it into a corrected VE table for you.

Workflow example:
- If trims show +8% at 3000 rpm / 65 kPa, I will increase VE in that cell by ~8% (then smooth neighboring cells).
- If trims show -4% at 4000 rpm / 80 kPa, I will reduce VE in that cell by ~4%.

Goal:
Iterate until trims are within ±5%. For final polish, ±2–3% is ideal.

Safety notes:
- Don’t chase trims on one short ride. Gather multiple logs in varied conditions.
- Ignore trims during transients (rapid throttle changes). Focus on steady-state holds.
- Always verify after applying corrections — repeat rides and smooth again.

