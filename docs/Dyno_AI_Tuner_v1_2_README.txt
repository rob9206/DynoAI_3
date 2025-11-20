
Dyno AI Tuner v1.2 — VE Apply + Diagnostics
===========================================

What’s new in v1.2
------------------
- **Integrated VE applier**: provide your base VE table(s) and get updated absolute VE front/rear, plus paste-ready blocks.
- **Diagnostics / anomaly detection**: flags spatial discontinuities, cyl fueling imbalance, low-MAP-only lean (possible exhaust leak), hot knock clusters, and low-voltage correlation.

Quick start (dyno bay)
---------------------
python /mnt/data/ai_tuner_toolkit_dyno_v1_2.py \
  --csv "/mnt/data/winpep_export.csv" \
  --outdir "/mnt/data" \
  --smooth_passes 2 \
  --clamp 15 \
  --rear_bias 2.5 \
  --rear_rule_deg 2.0 \
  --hot_extra -1.0 \
  --base_front "/mnt/data/FXDLS_Wheelie_VE_Base_Front.csv"

Outputs
-------
Tables (CSV):
- VE_Correction_Delta_DYNO.csv
- Spark_Adjust_Suggestion_Front.csv
- Spark_Adjust_Suggestion_Rear.csv
- AFR_Error_Map_Front.csv / AFR_Error_Map_Rear.csv
- Coverage_Front.csv / Coverage_Rear.csv

Paste-ready (tab-delimited):
- VE_Delta_PasteReady.txt     (percent delta)
- Spark_Front_PasteReady.txt  (deg delta)
- Spark_Rear_PasteReady.txt   (deg delta)
- VE_Front_Absolute_PasteReady.txt / VE_Rear_Absolute_PasteReady.txt (absolute VE if base provided)

WinPV-importable bases (if provided):
- VE_Front_Updated.csv
- VE_Rear_Updated.csv

Diagnostics:
- Diagnostics_Report.txt       (human-readable)
- Anomaly_Hypotheses.json      (machine-readable)

How diagnostics think
---------------------
- **Spatial discontinuity**: large cell change vs neighbors (robust z > 3.5) → data artifact or real airflow quirk.
- **Cyl fueling imbalance**: rear–front AFR error avg ≥ 3% in 2.5–3.8k @ 65–95 kPa → injector/VE bias candidates.
- **Low-MAP-only lean**: lean at 1.5–2.5k @ 35–50 kPa but not mid/high → suspect exhaust leak upstream.
- **Knock clusters**: knock ≥ 1.5° (hot cells prioritized) → enrich/pull timing in those bins.
- **Electrical correlation**: AFR error negatively correlated (r ≤ −0.4) with battery volts under load → injector latency/pump supply issues.

Tips
----
- Start clamp at ±15 %, tighten to ±7 % as surfaces converge.
- The rear rule (-2° in 2.8–3.6k @ 75–95 kPa, extra -1° when IAT≥120°F) is applied to the **rear spark suggestion** layer; still eyeball final spark.
- Re-check coverage grids; empty cells mean you didn’t hold those bins long enough.

