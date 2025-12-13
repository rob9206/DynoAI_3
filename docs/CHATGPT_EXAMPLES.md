# Sample ChatGPT Prompt with Text Export

This file demonstrates how to use the DynoAI text export with ChatGPT or other AI assistants.

## Example 1: General Analysis Request

**Prompt:**
```
I have dyno tuning results from my Harley-Davidson motorcycle. Can you analyze 
this data and provide specific recommendations for improvement?

================================================================================
DYNOAI AUTO-TUNE ANALYSIS REPORT
================================================================================

RUN INFORMATION
--------------------------------------------------------------------------------
Run ID: test_run
Timestamp: 2025-01-15T10:30:00Z
Data Source: simulation

PERFORMANCE SUMMARY
--------------------------------------------------------------------------------
Peak Horsepower: 95.50 HP @ 5200 RPM
Peak Torque: 102.30 lb-ft @ 3500 RPM
Total Samples: 1500
Duration: 45.0 seconds

AFR ANALYSIS
--------------------------------------------------------------------------------
Overall Status: BALANCED
Lean Cells: 12
Rich Cells: 8
OK Cells: 65
No Data Cells: 14

VE CORRECTION GRID (2D)
--------------------------------------------------------------------------------
Format: RPM | MAP bins (kPa)

RPM,30,40,50,60,70,80,90,100,110
1500,1.00,1.01,1.02,1.00,0.99,0.98,1.00,1.01,1.00
2000,1.01,1.02,1.03,1.01,0.98,0.97,0.99,1.02,1.01
2500,1.02,1.03,1.04,1.02,0.97,0.96,0.98,1.03,1.02
3000,1.01,1.02,1.05,1.03,0.96,0.95,0.97,1.04,1.03
3500,1.00,1.01,1.04,1.04,0.95,0.94,0.96,1.05,1.04
4000,0.99,1.00,1.03,1.05,0.94,0.93,0.95,1.06,1.05
4500,0.98,0.99,1.02,1.04,0.93,0.92,0.94,1.05,1.04
5000,0.97,0.98,1.01,1.03,0.94,0.93,0.95,1.04,1.03
5500,0.98,0.99,1.00,1.02,0.95,0.94,0.96,1.03,1.02
6000,0.99,1.00,0.99,1.01,0.96,0.95,0.97,1.02,1.01
6500,1.00,1.01,0.98,1.00,0.97,0.96,0.98,1.01,1.00

AFR ERROR GRID (2D)
--------------------------------------------------------------------------------
Format: RPM | AFR error in AFR points

RPM,30,40,50,60,70,80,90,100,110
1500,0.0,0.2,0.3,0.0,-0.2,-0.3,0.0,0.2,0.0
2000,0.2,0.3,0.5,0.2,-0.3,-0.5,-0.1,0.3,0.2
2500,0.3,0.5,0.6,0.3,-0.5,-0.6,-0.3,0.5,0.3
3000,0.2,0.3,0.7,0.5,-0.6,-0.7,-0.5,0.6,0.5
3500,0.0,0.2,0.6,0.6,-0.7,-0.8,-0.6,0.7,0.6
4000,-0.2,0.0,0.5,0.7,-0.8,-0.9,-0.7,0.8,0.7
4500,-0.3,-0.1,0.3,0.6,-0.9,-1.0,-0.8,0.7,0.6
5000,-0.5,-0.3,0.2,0.5,-0.8,-0.9,-0.7,0.6,0.5
5500,-0.3,-0.1,0.0,0.3,-0.7,-0.8,-0.6,0.5,0.3
6000,-0.2,0.0,-0.2,0.2,-0.6,-0.7,-0.5,0.3,0.2
6500,0.0,0.2,-0.3,0.0,-0.5,-0.6,-0.3,0.2,0.0

HIT COUNT GRID (2D)
--------------------------------------------------------------------------------
Format: RPM | Sample count per cell

RPM,30,40,50,60,70,80,90,100,110
1500,5,10,15,12,8,6,10,15,12
2000,8,12,18,15,10,8,12,18,15
2500,10,15,22,18,12,10,15,22,18
3000,12,18,25,22,15,12,18,25,22
3500,15,22,28,25,18,15,22,28,25
4000,12,18,25,28,22,18,25,32,28
4500,10,15,22,25,18,15,22,28,25
5000,8,12,18,22,15,12,18,25,22
5500,10,15,15,18,12,10,15,22,18
6000,8,12,10,15,8,6,12,18,15
6500,5,10,8,12,5,3,10,15,12

GRID CONFIGURATION
--------------------------------------------------------------------------------
RPM Bins: [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
MAP Bins: [30, 40, 50, 60, 70, 80, 90, 100, 110]
Grid Size: 11 x 9 = 99 cells
```

## Example 2: Specific Zone Analysis

**Prompt:**
```
Looking at this VE correction data, which RPM/MAP zones show the most significant 
lean condition (requiring fuel increase)? Should I prioritize these corrections?

[paste VE correction and AFR error grids here]
```

## Example 3: Performance Optimization

**Prompt:**
```
Based on this dyno data, what are the optimal RPM ranges for:
1. Maximum horsepower
2. Maximum torque
3. Best power-to-weight efficiency

Here's my analysis data:
[paste text export here]
```

## Example 4: Before/After Comparison

**Prompt:**
```
I made VE corrections and ran the dyno again. Can you compare the before and 
after results and tell me if the corrections improved the tune?

BEFORE:
[paste first export]

AFTER:
[paste second export]

Please focus on:
1. AFR error reduction
2. Power gains
3. Overall tune quality
```

## Expected AI Response Quality

With the structured text export, AI assistants can:

✓ Identify problematic zones with high AFR error
✓ Suggest specific VE corrections for lean/rich areas
✓ Analyze power band characteristics
✓ Compare multiple runs for improvement tracking
✓ Provide tuning recommendations based on data patterns
✓ Explain technical concepts in the context of your specific data

## Tips for Best Results

1. **Be specific**: Ask targeted questions about particular RPM/MAP zones
2. **Provide context**: Mention your motorcycle model, modifications, goals
3. **Request explanations**: Ask the AI to explain why it recommends certain changes
4. **Compare runs**: Share before/after data to track improvements
5. **Ask for priorities**: Which corrections should you apply first?

## Real-World Example Response

When you share the text export with an AI, you might get responses like:

> "Based on your VE correction grid, I can see several areas needing attention:
> 
> **High Priority Zones** (Significant Lean Condition):
> - 3000-4500 RPM @ 50-60 kPa: AFR errors of +0.6 to +0.7, requiring 4-5% VE increase
> - These zones are critical for mid-range acceleration
> 
> **Medium Priority** (Rich Condition):
> - 3000-5000 RPM @ 70-90 kPa: AFR errors of -0.8 to -1.0, needing 6-7% VE decrease
> - These affect WOT performance but are safer to leave slightly rich
> 
> **Recommendations**:
> 1. Apply the lean zone corrections first (safety critical)
> 2. Re-test and verify before adjusting rich zones
> 3. Your peak HP at 5200 RPM looks good - maintain current settings there"

This type of detailed, zone-specific analysis is possible thanks to the structured text export format!
