# Find Me Power - Quick Start Guide

## What Is It?

An automated analysis that tells you exactly where you can safely gain more horsepower from your tune.

## How to Use It

### Step 1: Run Your Normal Dyno Analysis

```bash
python ai_tuner_toolkit_dyno_v1_2.py --csv your_dyno_log.csv --outdir ./output
```

### Step 2: Check the Results

Look for `PowerOpportunities.json` in your output folder. Open it to see your opportunities.

### Step 3: Review Top Opportunities

The file shows opportunities sorted by estimated HP gain (biggest gains first):

```json
{
  "summary": {
    "total_opportunities": 7,
    "total_estimated_gain_hp": 34.16
  },
  "opportunities": [
    {
      "type": "Combined (AFR + Timing)",
      "rpm": 3500,
      "kpa": 95,
      "suggestion": "Lean by 1.7% AND advance 1.5°",
      "estimated_gain_hp": 6.60,
      "confidence": 100,
      "coverage": 95
    }
    // ... more opportunities
  ]
}
```

### Step 4: Make Changes Safely

**For AFR Changes:**
1. Find the cell at the specified RPM/kPa in your VE table
2. Apply HALF the suggested change first
3. Test on dyno
4. If safe, apply the other half

**For Timing Changes:**
1. Find the cell at the specified RPM/kPa in your spark table
2. Apply HALF the suggested advance first
3. Test on dyno and watch for knock
4. If no knock, apply the other half

**For Combined Changes:**
1. Apply AFR change first, test
2. Then apply timing change, test
3. Never apply both at once!

## Understanding the Output

### Opportunity Types

**"Lean AFR"** - You're running too rich, can lean out for more power
```
Example: "Lean by 2.1% (currently +4.2% rich)"
→ Reduce VE by 2.1% in that cell
```

**"Advance Timing"** - No knock detected, safe to advance timing
```
Example: "Advance timing by 2.0° (no knock detected)"
→ Add 2° to spark advance in that cell
```

**"Combined (AFR + Timing)"** - Can do both for maximum gain
```
Example: "Lean by 1.7% AND advance 1.5°"
→ Do AFR first, then timing
```

### Confidence Levels

- **100%**: Excellent data (50+ hits in that cell)
- **80-99%**: Good data (40-49 hits)
- **40-79%**: Adequate data (20-39 hits)

Higher confidence = safer to trust the suggestion.

### Coverage

Number of data points in that cell. More is better.
- **50+**: Excellent
- **30-49**: Good
- **20-29**: Adequate
- **<20**: Not analyzed (too risky)

## Safety Rules

The analysis follows these safety rules automatically:

✓ **Never suggests changes where knock was detected**
✓ **Only analyzes cells with 20+ data points**
✓ **Limits AFR changes to ±3% maximum**
✓ **Limits timing advances to +2° maximum**
✓ **All estimates are conservative**

## Quick Example

Let's say you see this opportunity:

```json
{
  "type": "Lean AFR",
  "rpm": 3000,
  "kpa": 65,
  "suggestion": "Lean by 2.0% (currently +4.0% rich)",
  "estimated_gain_hp": 3.5,
  "confidence": 95,
  "coverage": 48
}
```

**What it means:**
- At 3000 RPM and 65 kPa, you're running 4% rich
- You can safely lean by 2% (half the error)
- This should gain about 3.5 HP
- You have good data (48 hits, 95% confidence)

**What to do:**
1. Open your VE table
2. Find the cell at 3000 RPM / 65 kPa
3. Reduce VE by 1% (half of suggested 2%)
4. Test on dyno
5. If AFR is still rich and no issues, reduce another 1%

## Common Questions

**Q: Should I apply all the suggestions at once?**
A: NO! Apply one at a time, test each change.

**Q: What if I don't see many opportunities?**
A: Your tune might already be well optimized! Or you might need more dyno coverage.

**Q: Can I apply more than the suggested amount?**
A: Not recommended. The suggestions are already at safe limits.

**Q: What if I see knock after making a change?**
A: Immediately revert the change. The analysis is based on your current conditions.

**Q: Why are the HP estimates conservative?**
A: Safety first! Actual gains may be higher, but we'd rather underestimate.

**Q: Should I prioritize AFR or timing changes?**
A: AFR changes first (safer), then timing. Or follow the "Combined" suggestions.

## Pro Tips

1. **Start with highest-gain opportunities** in your most-used RPM range
2. **Make changes during same dyno session** so conditions are consistent
3. **Log everything** - write down what you changed and the results
4. **Re-run analysis after changes** to find new opportunities
5. **Watch for patterns** - if multiple cells suggest same direction, there may be a systematic issue

## Troubleshooting

**"No opportunities found"**
- Check if you have good dyno coverage (>20 hits per cell)
- Your tune might already be optimized
- Review Diagnostics_Report.txt for data quality issues

**"All opportunities are low confidence"**
- Need more dyno runs for better data
- Try doing more steady-state holds in those RPM/load ranges

**"Suggestions seem too aggressive"**
- Remember they're conservative and tested safe
- But always start with 50% of suggestion and test

## Next Steps

1. Review your top 3-5 opportunities
2. Pick one in your primary operating range
3. Apply 50% of the suggested change
4. Test on dyno
5. If safe, apply remaining 50%
6. Move to next opportunity
7. Re-run analysis to find more gains

## Remember

- **Test incrementally** - Never apply full changes at once
- **Monitor knock** - Always watch knock sensors
- **Verify AFR** - Make sure wideband is accurate
- **Keep notes** - Document every change
- **Stay safe** - When in doubt, be conservative

---

**Happy tuning! 🏍️💨**

