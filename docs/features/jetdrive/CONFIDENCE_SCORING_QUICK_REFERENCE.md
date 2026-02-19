# Tune Confidence Scoring - Quick Reference

## What is it?
A scoring system that evaluates your tune quality on a scale of 0-100% with a letter grade (A/B/C/D).

## Where to find it?
After running a tune analysis, check:
- **ConfidenceReport.json** - Full detailed report
- **Diagnostics_Report.txt** - Human-readable summary (at the top)
- Console output shows: `[OK] Tune Confidence: XX.X% (Grade X)`

## Understanding Your Score

### Letter Grades
| Grade | Score Range | Meaning |
|-------|-------------|---------|
| **A** | 85-100% | Excellent - Ready for deployment |
| **B** | 70-84% | Good - Minor improvements recommended |
| **C** | 50-69% | Fair - Additional data collection needed |
| **D** | 0-49% | Poor - Significant issues require attention |

### Score Components
Your overall score is calculated from:
- **Coverage (40%)** - Do you have enough data points? (≥10 hits per cell)
- **Consistency (30%)** - Is your data stable? (Low MAD = good)
- **Anomalies (15%)** - Are there unusual patterns or issues?
- **Clamping (15%)** - Are corrections hitting limits?

## What the Numbers Mean

### Coverage Percentage
- **>85%**: Excellent data coverage
- **60-85%**: Good coverage, some gaps
- **<60%**: Need more data collection

### MAD (Median Absolute Deviation)
- **<0.5**: Excellent consistency
- **0.5-1.0**: Good consistency
- **1.0-2.0**: Fair consistency, check for issues
- **>2.0**: Poor consistency, investigate mechanical problems

### Clamp Percentage
- **0-5%**: Normal, minor corrections
- **5-10%**: Acceptable, some large corrections
- **10-20%**: Consider increasing clamp limits
- **>20%**: Investigate root causes

## Common Recommendations

### "Collect more data in these areas"
**What it means:** Some cells don't have enough data points  
**What to do:** Run more dyno pulls covering those RPM/load ranges

### "Data inconsistent, check for mechanical issues"
**What it means:** Your data varies too much between runs  
**What to do:** 
- Check for vacuum leaks
- Verify sensor calibration
- Ensure consistent test conditions
- Look for intermittent mechanical issues

### "Consider increasing clamp limits"
**What it means:** Many corrections are hitting the safety limits  
**What to do:**
- Review the corrections to ensure they're reasonable
- If corrections look valid, increase `--clamp` parameter
- Default is 7%, try 10-15% for analysis mode

### "High-severity anomalies detected"
**What it means:** Unusual patterns found in your data  
**What to do:** Review `Anomaly_Hypotheses.json` for specific issues

## Region Breakdown

The report breaks down your tune by operating region:

### Idle (1000-2000 RPM, 20-40 kPa)
- Light throttle, low load conditions
- Important for driveability

### Cruise (2000-3500 RPM, 40-70 kPa)
- Normal riding conditions
- Most time spent here

### WOT (3000-6500 RPM, 85-105 kPa)
- Wide Open Throttle, high load
- Critical for performance and safety

## Example Reports

### Grade A Example
```
Overall Score: 92.5%
Letter Grade: A - Excellent - Ready for deployment

Coverage: 95.2% of cells well-covered
Consistency: Average MAD = 0.42 (excellent)
Anomalies: 1 minor issue detected
Clamping: 2.3% of cells clamped

Recommendation: Tune quality is excellent. No major improvements needed.
```

### Grade C Example
```
Overall Score: 58.3%
Letter Grade: C - Fair - Additional data collection needed

Coverage: 62.1% of cells well-covered
Consistency: Average MAD = 1.35 (fair)
Anomalies: 4 issues detected
Clamping: 8.7% of cells clamped

Recommendations:
1. Focus data collection on: idle (45% covered), wot (52% covered)
2. Data consistency could be improved in cruise region (MAD=1.8)
3. Review anomalies in Anomaly_Hypotheses.json
```

## Tips for Improving Your Score

### To Improve Coverage
1. Run more dyno pulls
2. Cover full RPM range
3. Test at various throttle positions
4. Ensure consistent operating temperature

### To Improve Consistency
1. Allow engine to fully warm up
2. Use consistent fuel
3. Maintain stable ambient conditions
4. Check sensor calibration
5. Fix any mechanical issues first

### To Reduce Clamping
1. Start with conservative base tune
2. Make iterative adjustments
3. Consider increasing clamp limits if corrections are valid
4. Investigate large corrections before applying

### To Reduce Anomalies
1. Review flagged cells in detail
2. Verify sensor readings
3. Check for data logging errors
4. Ensure stable test conditions

## Performance Note
Confidence calculation takes <0.1ms and uses only pre-calculated data. No impact on tuning process performance.

## Questions?
- Check `ConfidenceReport.json` for detailed methodology
- Review `Diagnostics_Report.txt` for full analysis
- Consult `Anomaly_Hypotheses.json` for specific issues

