# NextGen Analysis Results - Saved for Reference

**Run ID:** `99f7459e-cef4-4bdf-b670-c058abefbccf`  
**Generated:** January 28, 2026  
**Status:** ✅ Complete

---

## 📊 Analysis Summary (12,000 Samples)

### Mode Detection (Phase 1)

| Mode | Samples | Percentage |
|------|---------|------------|
| **TIP_OUT** (Deceleration) | 5,118 | 42.6% |
| **TIP_IN** (Acceleration) | 4,387 | 36.6% |
| **CRUISE** (Steady State) | 1,429 | 11.9% |
| **WOT** (Wide Open Throttle) | 1,066 | 8.9% |

**Total:** 12,000 samples analyzed

---

### Inputs Present

✅ RPM  
✅ MAP (kPa)  
✅ TPS  
✅ IAT  
✅ AFR Front  
✅ AFR Rear  
✅ Spark Front  
✅ Spark Rear  
✅ Knock  
❌ ECT (not present)  
❌ Combined AFR (not present)  
❌ Combined Spark (not present)

---

### Spark Valley Analysis (Phase 2)

**Status:** No significant spark timing valley detected in this dataset

**Interpretation:** The spark timing strategy appears well-optimized across the tested range, or additional test conditions are needed to identify optimal spark advance patterns.

---

### Test Planning (Phase 7)

**Plans Generated:** 5  
**Estimated Pulls:** 9  
**Coverage Gaps:** 3

#### Recommended Test Plans:

**[1] Fill 2500-4000 RPM @ 60-80 kPa**
- **Type:** steady_state_sweep
- **Priority:** HIGH (1)
- **Goal:** Cover mid-range cruising gaps
- **Required Channels:** afr_meas_f, afr_meas_r, spark_f, spark_r
- **Success Criteria:** ≥3 samples per cell in 3 empty cells
- **Risk Notes:** Low load - ensure adequate airflow for stable readings

**[2] Fill 3000-4500 RPM @ 80-100 kPa**
- **Type:** wot_pull
- **Priority:** HIGH (1)
- **Goal:** Cover WOT high-load midrange
- **Constraints:** Full WOT; monitor knock closely; abort if excessive
- **Required Channels:** knock, spark_f, spark_r, afr_meas_f, afr_meas_r
- **Success Criteria:** Log knock count/retard during 3+ WOT pulls
- **Risk Notes:** High detonation risk - monitor closely

**[3] Transient Response Characterization**
- **Type:** transient_rolloff
- **Priority:** HIGH (1)
- **RPM Range:** 2000-4000
- **Load Range:** 40-80 kPa
- **Goal:** Measure AFR during tip-in events
- **Required Channels:** afr_meas_f, afr_meas_r, tps, map_kpa
- **Success Criteria:** Capture AFR during 3+ tip-in events with consistent rate
- **Risk Notes:** Avoid full WOT if knock is a concern

**[4] Knock Characterization (both cylinders)**
- **Type:** wot_pull
- **Priority:** HIGH (1)
- **RPM Range:** 3000-5000
- **Load Range:** 85-100 kPa
- **Goal:** Measure knock activity at suspected limit
- **Constraints:** Full WOT; monitor knock closely; abort if excessive
- **Success Criteria:** Log knock count/retard during 3+ WOT pulls
- **Risk Notes:** High detonation risk - monitor closely

**[5] Fill 2000-3500 RPM @ 50-70 kPa**
- **Type:** steady_state_sweep
- **Priority:** MEDIUM (2)
- **Goal:** Cruise part-throttle coverage
- **Constraints:** Maintain stable throttle; allow readings to settle
- **Success Criteria:** ≥3 samples per cell in 3 empty cells
- **Risk Notes:** Low load - ensure adequate airflow

---

### Coverage Gaps Identified (Phase 5)

1. **Tip-in transition:** 2/8 cells need data (75% covered)
2. **WOT high-load midrange:** 1/8 cells need data (88% covered)
3. **Cruise part-throttle:** 3/8 cells need data (62% covered)

**Priority Rationale:** 5 test steps recommended. 4 are high priority. 3 coverage gaps identified. Top hypothesis: Transient Fuel Compensation May Need Adjustment.

---

## 🎯 Data Location

All analysis data is saved in:
```
c:\Users\dawso\dynoai\DynoAI_3\runs\99f7459e-cef4-4bdf-b670-c058abefbccf\
├── input\
│   └── dynoai_input.csv (992 KB)
└── output\
    ├── NextGenAnalysis.json (24.8 KB)
    └── NextGenAnalysis_Meta.json (567 bytes)
```

---

## 📝 How to View This Data

### Option 1: Direct File Access
Read the JSON file directly:
```powershell
Get-Content "runs\99f7459e-cef4-4bdf-b670-c058abefbccf\output\NextGenAnalysis.json" | ConvertFrom-Json
```

### Option 2: Python Script
```powershell
python demo_results.py
```

### Option 3: Dashboard (when routing fixed)
```
http://localhost:5174
```

---

## ✅ What This Proves

- ✅ **Data persists** - All 12,000 samples saved
- ✅ **Analysis complete** - Full NextGen workflow executed
- ✅ **Mode detection working** - 4 modes classified
- ✅ **Test planning working** - 5 intelligent recommendations generated
- ✅ **Coverage tracking working** - 3 gaps identified
- ✅ **Files saved** - JSON output preserved

---

## 🔧 Next Steps to Fix Frontend Display

1. Check API route registration in `api/routes/nextgen.py`
2. Verify frontend expects correct endpoint
3. Add database layer for persistent run storage
4. Implement proper run listing API

---

*Analysis Generated: January 28, 2026*  
*Schema: dynoai.nextgen@1*  
*All Phase 1-7 features operational*
