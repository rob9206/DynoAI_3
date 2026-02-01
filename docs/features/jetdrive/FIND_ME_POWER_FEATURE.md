# Find Me Power Analysis Feature

## Overview

The "Find Me Power" feature is an automated analysis tool that identifies safe opportunities to gain additional horsepower from your tune. It analyzes AFR error maps, coverage data, spark timing suggestions, and knock data to provide specific, actionable recommendations.

## How It Works

The analysis examines each cell in your tuning map and looks for three types of power opportunities:

### 1. **Lean AFR Opportunities**
- Identifies cells running >2% rich with good coverage (>20 hits)
- Suggests leaning by up to 50% of the error (capped at 3%)
- Estimates power gain at ~2% HP per 1% leaner AFR

**Example:**
```
Location: 3000 RPM @ 65 kPa
Currently: +4.5% rich
Suggestion: Lean by 2.2%
Estimated Gain: 3.3 HP
```

### 2. **Timing Advance Opportunities**
- Identifies cells with no knock activity (< 0.1° retard)
- Suggests conservative timing advance (up to 2° per cell)
- Estimates power gain at ~3% HP per degree of advance

**Example:**
```
Location: 3500 RPM @ 80 kPa
Currently: No knock detected
Suggestion: Advance timing by 2.0°
Estimated Gain: 5.1 HP
```

### 3. **Combined Opportunities**
- Identifies cells that are both rich AND knock-free
- Suggests both AFR leaning and timing advance
- Provides multiplicative power gains (with conservative estimates)

**Example:**
```
Location: 4000 RPM @ 95 kPa
Currently: +3.5% rich, no knock
Suggestion: Lean by 1.7% AND advance 1.5°
Estimated Gain: 6.6 HP
```

## Safety Features

The analysis includes multiple safety checks to ensure all suggestions are conservative:

1. **Knock Detection**: Never suggests changes in cells with knock ≥ 0.5°
2. **Coverage Threshold**: Only suggests changes for cells with ≥20 data points
3. **AFR Limits**: Maximum ±3% AFR change per suggestion
4. **Timing Limits**: Maximum +2° timing advance per suggestion
5. **Conservative Estimates**: All power gain estimates are intentionally conservative

## Output Format

The feature generates a `PowerOpportunities.json` file with:

```json
{
  "summary": {
    "total_opportunities": 7,
    "total_estimated_gain_hp": 34.16,
    "analysis_date": "2025-12-15T..."
  },
  "opportunities": [
    {
      "type": "Combined (AFR + Timing)",
      "rpm": 3500,
      "kpa": 95,
      "suggestion": "Lean by 1.7% AND advance 1.5°",
      "estimated_gain_hp": 6.60,
      "confidence": 100,
      "coverage": 95,
      "current_hp": 95.0,
      "details": {
        "afr_error_pct": 3.35,
        "suggested_afr_change_pct": -1.68,
        "advance_deg": 1.5,
        "knock_front": 0.0,
        "knock_rear": 0.0
      }
    }
    // ... more opportunities
  ],
  "safety_notes": [
    "All suggestions are conservative and prioritize engine safety",
    "Test changes incrementally and monitor for knock",
    "Verify AFR targets are appropriate for your fuel and application",
    "Maximum suggested changes: ±3% AFR, +2° timing per cell"
  ]
}
```

## Usage

The Find Me Power analysis runs automatically as part of the standard tuning workflow:

```bash
python ai_tuner_toolkit_dyno_v1_2.py --csv your_dyno_log.csv --outdir ./output
```

The analysis runs after diagnostics and generates `PowerOpportunities.json` in the output directory.

## Interpreting Results

### Confidence Levels
- **100%**: Cell has ≥50 data points (excellent coverage)
- **80-99%**: Cell has 40-49 data points (good coverage)
- **40-79%**: Cell has 20-39 data points (adequate coverage)

### Priority Order
Opportunities are automatically sorted by estimated HP gain (highest first). Focus on:
1. Top 3-5 opportunities for maximum impact
2. Cells in your primary operating range (cruising/acceleration)
3. Combined opportunities (AFR + Timing) for best gains

### Implementation Strategy

**Incremental Approach (Recommended):**
1. Start with the highest-gain opportunity
2. Make 50% of the suggested change
3. Test on dyno and verify no knock
4. If safe, apply remaining 50%
5. Move to next opportunity

**Example:**
```
Suggestion: Lean by 2.0%
Step 1: Apply -1.0% change
Step 2: Test and verify
Step 3: Apply additional -1.0% if safe
```

## Limitations

1. **Conservative by Design**: Estimates are intentionally conservative. Actual gains may be higher.
2. **Cell-Level Analysis**: Doesn't account for transient behavior between cells.
3. **Fuel Dependent**: Assumes current fuel octane is appropriate for timing advances.
4. **No Load Simulation**: Cannot predict behavior under different atmospheric conditions.

## Best Practices

### Before Making Changes
- ✓ Verify your AFR targets are appropriate for your fuel
- ✓ Check that your wideband sensors are calibrated
- ✓ Ensure dyno data quality is good (no sensor glitches)
- ✓ Review knock data carefully

### When Applying Changes
- ✓ Make changes incrementally (50% at a time)
- ✓ Test each change on the dyno before moving to next
- ✓ Monitor knock sensors continuously
- ✓ Log EGT if available (watch for excessive heat)
- ✓ Keep notes on what you changed

### After Changes
- ✓ Run full dyno sweep to verify gains
- ✓ Test in real-world conditions
- ✓ Monitor for detonation during street testing
- ✓ Re-run analysis to find additional opportunities

## Technical Details

### Algorithm Overview
```python
For each cell in tuning map:
    1. Check coverage >= 20 hits
    2. Check knock < 0.5°
    3. Calculate average AFR error (front + rear)
    4. If rich > 2%:
        - Suggest leaning by 50% of error (max 3%)
        - Estimate HP gain
    5. If no knock and timing not already advanced:
        - Suggest +2° advance
        - Estimate HP gain
    6. If both conditions met:
        - Suggest combined change
        - Estimate combined HP gain
    7. Sort all opportunities by HP gain
    8. Return top 10
```

### Power Gain Estimation

**AFR Leaning:**
```
HP_gain = Current_HP × (Lean_% × 0.02)
```

**Timing Advance:**
```
HP_gain = Current_HP × (Advance_deg × 0.03)
```

**Combined:**
```
HP_gain = AFR_gain + (Timing_gain × 0.8)
```
*Note: Timing gain is reduced by 20% when combined to be conservative*

## Example Output

```
[OK] Found 7 power opportunities, estimated total gain: 34.16 HP

Top Opportunities:
1. Combined (AFR + Timing) @ 3500 RPM / 95 kPa
   Lean by 1.7% AND advance 1.5° → +6.60 HP

2. Combined (AFR + Timing) @ 2500 RPM / 50 kPa
   Lean by 2.1% AND advance 1.5° → +5.89 HP

3. Advance Timing @ 3500 RPM / 95 kPa
   Advance timing by 2.0° → +5.70 HP
```

## Integration with Existing Workflow

The Find Me Power feature integrates seamlessly with the existing DynoAI toolkit:

1. **Input**: Uses existing AFR error maps, coverage data, and spark suggestions
2. **Processing**: Runs after diagnostics, before visualization
3. **Output**: Adds `PowerOpportunities.json` to standard output manifest
4. **No Breaking Changes**: Completely optional, doesn't affect existing outputs

## Testing

A comprehensive test suite is included in `test_power_opportunities.py`:

```bash
python test_power_opportunities.py
```

The test verifies:
- ✓ Identifies rich cells correctly
- ✓ Identifies timing advance opportunities
- ✓ Finds combined opportunities
- ✓ Avoids cells with knock
- ✓ Avoids cells with low coverage
- ✓ Respects safety limits
- ✓ Generates positive HP estimates

## Future Enhancements

Potential improvements for future versions:

1. **Transient Analysis**: Account for acceleration/deceleration behavior
2. **Temperature Compensation**: Adjust suggestions based on IAT/ECT
3. **Fuel Quality Detection**: Adjust timing limits based on detected fuel quality
4. **Multi-Iteration Planning**: Suggest optimal sequence for multiple changes
5. **Risk Scoring**: Add risk assessment for each opportunity
6. **Visual Heatmap**: Generate visual map of power opportunities

## Support

For questions or issues with the Find Me Power feature:
1. Check the `Diagnostics_Report.txt` for data quality issues
2. Verify your dyno log has good coverage (>20 hits per cell)
3. Review the safety notes in `PowerOpportunities.json`
4. Consult with a professional tuner for aggressive changes

## License

This feature is part of the DynoAI toolkit and follows the same license terms.

---

**Remember: Safety First!** 

All suggestions are conservative starting points. Always test changes incrementally and monitor for knock. When in doubt, consult with an experienced tuner.

