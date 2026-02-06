# VE Correction Apply Workflow Guide

This guide explains the 5-step auto-tune wizard and how to apply VE corrections to your base tune.

## Overview

The Apply Workflow takes live VE corrections collected during dyno pulls and applies them to your imported base tune (PVV file). It includes safety checks, confidence-based clamping, and dual-cylinder support.

## The 5-Step Wizard

### Step 1: Setup

Import your base tune before collecting data:

- **PVV file**: Drag and drop a Power Vision export (.pvv) containing your VE tables
- **Engine preset**: Or select a preset (e.g., Harley M8) for default VE/AFR values

The wizard validates that VE tables are present before proceeding.

### Step 2: Collect

Run dyno pulls to collect AFR data:

- Start the simulator or connect to live hardware
- Perform WOT pulls across the RPM range
- The coverage meter shows which zones have enough data
- Target: 75%+ weighted coverage for reliable corrections

### Step 3: Analyze

Click "Analyze" to calculate corrections:

- Compares measured AFR to target AFR
- Calculates VE delta per cell (7% per AFR point)
- Generates per-cylinder corrections (front and rear)

### Step 4: Review

Preview changes before applying:

- **Before/After comparison**: See how each cell will change
- **Confidence badges**: High/Medium/Low based on hit counts
- **Warnings**: Cells with low data or extreme corrections
- **Block reasons**: Issues that prevent applying (e.g., missing base VE)

### Step 5: Apply

Confirm and export:

- Corrections are applied with confidence-based clamping
- Low-confidence cells get smaller corrections (inch toward correct)
- Cells with <3 hits are skipped
- Download the corrected VE tables in PVV format

## Safety Features

### Zone Classification

Cells are classified by operating region:

| Zone | MAP (kPa) | RPM | Description |
|------|-----------|-----|-------------|
| Cruise | 31-69 | 1200-5500 | Steady-state riding |
| Part Throttle | 70-94 | 1200-5500 | Roll-on acceleration |
| WOT | 95+ | 1200-5500 | Full power pulls |
| Decel | ≤30 | 1200-5500 | Engine braking |
| Edge | Any | <1200 or >5500 | Idle/redline |

### Confidence-Based Clamping

Corrections are clamped based on data quality:

- **High confidence** (100+ hits): Up to ±10% correction
- **Medium confidence** (20-99 hits): Up to ±5% correction
- **Low confidence** (3-19 hits): Up to ±2% correction
- **Skip** (<3 hits): No correction applied

### VE Bounds

Final VE values are bounded to safe ranges:

- **Stock preset**: 40-120 VE
- **Performance preset**: 35-130 VE
- **Race preset**: 30-140 VE

### Cylinder Balance

The workflow checks for systematic front/rear imbalance:

- Warning if >3% systematic bias between cylinders
- Per-cell balance shown in the review panel

## Troubleshooting

### "Import a tune first" alert

You must import a base tune (PVV or preset) before analyzing or triggering pulls.

### Low coverage warning

Run more pulls to cover more zones. Focus on:
- Different RPM ranges
- Various throttle positions
- Both cylinders equally

### Extreme correction blocked

If a cell needs >25% correction, it's blocked. This usually indicates:
- Bad AFR sensor data
- Incorrect target AFR
- Mechanical issue

## Tips

1. **Start with a known-good base tune** - Don't apply corrections to a tune that's already far off
2. **Run multiple pulls** - More data = higher confidence = larger corrections allowed
3. **Check cylinder balance** - Large imbalances may indicate a mechanical issue
4. **Apply incrementally** - Multiple sessions with smaller corrections are safer than one big change
