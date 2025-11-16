# Reference VE Tables & Sample Data

This directory contains base VE tables and sample dyno logs for testing.

## Expected Files

### Base VE Tables
- `FXDLS_Wheelie_VE_Base_Front_fixed.csv` - Front cylinder base VE (corrected)
- `FXDLS_Wheelie_VE_Base_Front.csv` - Front cylinder base VE (original)
- `FXDLS_Wheelie_Spark_Delta.csv` - Spark timing deltas
- `FXDLS_Wheelie_AFR_Targets.csv` - Target AFR by RPM/kPa

### Sample Dyno Logs
- `WinPEP_Sample.csv` - Sample dyno log for testing
- `WinPEP_Log_Sample.csv` - Alternative sample format

## File Formats

### VE Tables
- **Format:** CSV with RPM in first column, kPa values as column headers
- **Precision:** 4 decimal places
- **Example:**
```
RPM,40,45,50,55,60
1000,45.2500,46.1250,47.0000,47.8750,48.7500
1500,46.0000,46.8750,47.7500,48.6250,49.5000
```

### Factor Tables (VE Corrections)
- **Format:** Percentage values (±XX.XXXX)
- **Dimensions:** Must match base table dimensions
- **Example:**
```
RPM,40,45,50,55,60
1000,0.0000,1.2500,2.5000,-1.0000,0.5000
1500,0.7500,-0.5000,1.0000,0.0000,-1.5000
```

### WinPEP CSV Logs
- **Required Columns:** rpm, map_kpa, afr_cmd_f, afr_cmd_r, afr_meas_f, afr_meas_r, ve_f, ve_r, spark_f, spark_r
- **Format:** Comma-separated values with header row

## Usage

### With CLI Engine
```bash
python core/ai_tuner_toolkit_dyno_v1_2.py \
    --csv tables/WinPEP_Sample.csv \
    --base_front tables/FXDLS_Wheelie_VE_Base_Front.csv \
    --outdir outputs/run1
```

### With VE Operations
```python
from core.ve_operations import VEApply

VEApply().apply(
    base_ve_path='tables/FXDLS_Wheelie_VE_Base_Front.csv',
    factor_path='outputs/run1/VE_Correction_Delta_DYNO.csv',
    output_path='outputs/run1/VE_Front_Updated.csv',
    max_adjust_pct=7.0
)
```

## Safety Notice

This directory is **read-only by default**. Do not overwrite base tables.

Use `VEApply` to create updated versions, preserving originals for rollback.
