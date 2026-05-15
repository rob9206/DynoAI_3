# TuneLab Autotune F1 — plan

**Plan version:** v2.0.1

## Changelog

- **v2.0.1** — Fixed `afr_target_source` default — was nonsense string `static_13.2`, now references the actual MAP-indexed target curve name `static_map_curve_v1`. Added regression test.

---

## CLI `argparse` (excerpt)

| Flag | Required | Description |
|------|----------|-------------|
| `--afr-target-source <str>` | no | `"static_map_curve_v1"` (default — the MAP-indexed target curve in `autotune_workflow.py::analyze_afr`) or `"from_tune.AFR_Target"` (F1.1). Do NOT use `"static_13.2"` — no static 13.2 target exists anywhere in the pipeline. |

_(Other CLI flags, flow, and stdout contract: align with the current `tools/autotune/tunelab_entrypoint.py` and `.cursor/plans/f1_autotune_preview_cli_6154b20c.plan.md` as implemented.)_

---

## `correction_summary.json` — schema example (excerpt)

```json
{
  "schema_version": 1,
  "afr_target_source": "static_map_curve_v1"
}
```

---

## Tests

| Test | Notes |
|------|--------|
| `test_cli_summary_schema_v1_fields_present` | After a successful CLI run, assert `correction_summary.json` includes all required schema v1 fields and types. |
| `test_cli_afr_target_source_defaults_to_static_map_curve_v1` | Run CLI without `--afr-target-source`; assert `correction_summary.json` field equals `"static_map_curve_v1"` exactly. Regression guard against the "static_13.2" bug. |
