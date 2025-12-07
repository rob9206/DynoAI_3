# Implementation Specification: Cam Profile Pattern Matching

_Version: 1.0 | Status: Draft | Last Updated: 2025-12-06_

## Executive Summary

This specification defines a pattern-matching system that generates cam-specific VE base maps by analyzing known cam profiles and their documented tuning requirements. Instead of starting from generic maps that require 3-4 autotune cycles, DynoAI will provide educated starting points that reduce dyno time by 50-70%.

---

## Problem Statement

### Current Pain Point
Cam selection fundamentally changes VE table requirements, and tuners start from inadequate baseline maps:
- Generic base maps require **3-4 full autotune cycles** to converge
- High-overlap cams cause **severe driveability issues** with stock VE tables
- Professional tuners spend **3.5-6+ hours** on Stage 2+ tunes largely because of poor starting points
- Pattern is predictable: "S&S 585 cams = +25-35% upper RPM VE" yet no tool applies this knowledge

### Documented Evidence
- Stage progression follows **predictable VE scaling**:
  - Stage 1 (air/exhaust): +8-15% VE
  - Stage 2 (+cam): +15-25% VE
  - Stage 3 (+big bore): +20-35% VE
- Cam-specific requirements are **well-documented** in tuner forums and manufacturer specs
- High-overlap cams require **specific compensations**: richer idle, advanced timing, higher idle RPM

### Target Outcome
Generate 70-90% accurate VE starting maps based on declared cam profile, reducing dyno convergence time from 4+ hours to 1-2 hours.

---

## Technical Approach

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│               Cam Profile Pattern Matching                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Cam Profile Database                                      │  │
│  │  - Manufacturer specs (lift, duration, overlap)           │  │
│  │  - Community-validated VE adjustments                     │  │
│  │  - Known tuning patterns                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Pattern Matcher                                           │  │
│  │  - Match user input to known profiles                     │  │
│  │  - Interpolate for unknown cams based on specs            │  │
│  │  - Apply mod-stack adjustments (air cleaner, exhaust)    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ VE Map Generator                                          │  │
│  │  - Generate cam-specific VE suggestions                   │  │
│  │  - Apply overlap compensation for idle/low-RPM            │  │
│  │  - Include confidence scores per region                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│  Output: Cam_Baseline_VE_Front.csv                              │
│          Cam_Baseline_VE_Rear.csv                               │
│          Cam_Profile_Report.json                                │
│          Cam_Tuning_Recommendations.txt                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Cam Profile Classification

Cams are classified into categories based on their characteristics:

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class CamCategory(Enum):
    """Cam classification by aggressiveness."""
    STOCK = "stock"
    MILD = "mild"           # Bolt-in, minimal overlap increase
    MODERATE = "moderate"   # Noticeable overlap, needs tune
    AGGRESSIVE = "aggressive"  # High overlap, significant idle impact
    RACE = "race"           # Extreme overlap, poor street manners


@dataclass
class CamProfile:
    """Complete cam specification."""
    # Identity
    manufacturer: str
    model: str
    part_number: Optional[str] = None
    
    # Intake specs
    intake_lift: float          # inches
    intake_duration: float      # degrees @ 0.053" lift
    intake_open_btdc: float     # degrees before TDC
    intake_close_abdc: float    # degrees after BDC
    
    # Exhaust specs
    exhaust_lift: float
    exhaust_duration: float
    exhaust_open_bbdc: float    # degrees before BDC
    exhaust_close_atdc: float   # degrees after TDC
    
    # Calculated/derived
    overlap: float = None       # Calculated from open/close points
    lsa: float = None           # Lobe separation angle
    
    # Classification
    category: CamCategory = CamCategory.MODERATE
    
    # Tuning hints (from community/manufacturer data)
    ve_adjustment_low: float = 0.0    # % adjustment 1500-2500 RPM
    ve_adjustment_mid: float = 0.0    # % adjustment 2500-4000 RPM
    ve_adjustment_high: float = 0.0   # % adjustment 4000-6000+ RPM
    idle_rpm_target: int = 850        # Recommended idle RPM
    timing_advance_idle: float = 0.0  # Timing adjustment at idle
    
    def __post_init__(self):
        """Calculate derived values."""
        if self.overlap is None:
            # Overlap = intake open BTDC + exhaust close ATDC
            self.overlap = self.intake_open_btdc + self.exhaust_close_atdc
```

---

## Cam Profile Database

### Database Schema

```python
CAM_DATABASE = {
    # Stock/Baseline Reference
    "STOCK_TC96": CamProfile(
        manufacturer="Harley-Davidson",
        model="Stock Twin Cam 96",
        intake_lift=0.472,
        intake_duration=200,
        intake_open_btdc=10,
        intake_close_abdc=30,
        exhaust_lift=0.472,
        exhaust_duration=210,
        exhaust_open_bbdc=45,
        exhaust_close_atdc=5,
        category=CamCategory.STOCK,
        ve_adjustment_low=0,
        ve_adjustment_mid=0,
        ve_adjustment_high=0,
        idle_rpm_target=800,
    ),
    
    # S&S Cycle Cams
    "SS_475": CamProfile(
        manufacturer="S&S Cycle",
        model="475 Bolt-In",
        part_number="330-0626",
        intake_lift=0.475,
        intake_duration=212,
        intake_open_btdc=16,
        intake_close_abdc=36,
        exhaust_lift=0.475,
        exhaust_duration=218,
        exhaust_open_bbdc=51,
        exhaust_close_atdc=7,
        overlap=23,  # Front cylinder
        category=CamCategory.MILD,
        ve_adjustment_low=8,
        ve_adjustment_mid=12,
        ve_adjustment_high=10,
        idle_rpm_target=875,
        timing_advance_idle=2,
    ),
    
    "SS_510": CamProfile(
        manufacturer="S&S Cycle",
        model="510 Gear Drive",
        part_number="330-0624",
        intake_lift=0.510,
        intake_duration=218,
        intake_open_btdc=20,
        intake_close_abdc=38,
        exhaust_lift=0.510,
        exhaust_duration=228,
        exhaust_open_bbdc=56,
        exhaust_close_atdc=12,
        overlap=32,
        category=CamCategory.MODERATE,
        ve_adjustment_low=12,
        ve_adjustment_mid=18,
        ve_adjustment_high=15,
        idle_rpm_target=925,
        timing_advance_idle=4,
    ),
    
    "SS_585": CamProfile(
        manufacturer="S&S Cycle",
        model="585 Easy Start",
        part_number="330-0630",
        intake_lift=0.585,
        intake_duration=244,
        intake_open_btdc=30,
        intake_close_abdc=54,
        exhaust_lift=0.585,
        exhaust_duration=252,
        exhaust_open_bbdc=64,
        exhaust_close_atdc=28,
        overlap=58,
        category=CamCategory.AGGRESSIVE,
        ve_adjustment_low=18,
        ve_adjustment_mid=28,
        ve_adjustment_high=35,
        idle_rpm_target=1000,
        timing_advance_idle=6,
    ),
    
    # Wood Performance Cams
    "WOOD_TW222": CamProfile(
        manufacturer="Wood Performance",
        model="TW-222",
        intake_lift=0.510,
        intake_duration=216,
        intake_open_btdc=14,
        intake_close_abdc=42,
        exhaust_lift=0.490,
        exhaust_duration=222,
        exhaust_open_bbdc=48,
        exhaust_close_atdc=14,
        overlap=28,
        category=CamCategory.MILD,
        ve_adjustment_low=6,
        ve_adjustment_mid=10,
        ve_adjustment_high=12,
        idle_rpm_target=850,
        timing_advance_idle=2,
    ),
    
    "WOOD_TW555": CamProfile(
        manufacturer="Wood Performance",
        model="TW-555",
        intake_lift=0.550,
        intake_duration=232,
        intake_open_btdc=24,
        intake_close_abdc=48,
        exhaust_lift=0.530,
        exhaust_duration=238,
        exhaust_open_bbdc=58,
        exhaust_close_atdc=20,
        overlap=44,
        category=CamCategory.MODERATE,
        ve_adjustment_low=15,
        ve_adjustment_mid=22,
        ve_adjustment_high=28,
        idle_rpm_target=950,
        timing_advance_idle=5,
    ),
    
    # Feuling Cams
    "FEULING_543": CamProfile(
        manufacturer="Feuling",
        model="543 Reaper",
        part_number="1020",
        intake_lift=0.543,
        intake_duration=222,
        intake_open_btdc=18,
        intake_close_abdc=44,
        exhaust_lift=0.543,
        exhaust_duration=228,
        exhaust_open_bbdc=54,
        exhaust_close_atdc=14,
        overlap=32,
        category=CamCategory.MODERATE,
        ve_adjustment_low=10,
        ve_adjustment_mid=15,
        ve_adjustment_high=20,
        idle_rpm_target=900,
        timing_advance_idle=3,
    ),
    
    "FEULING_574": CamProfile(
        manufacturer="Feuling",
        model="574 Chain Drive",
        part_number="1012",
        intake_lift=0.574,
        intake_duration=232,
        intake_open_btdc=24,
        intake_close_abdc=48,
        exhaust_lift=0.574,
        exhaust_duration=240,
        exhaust_open_bbdc=60,
        exhaust_close_atdc=20,
        overlap=44,
        category=CamCategory.MODERATE,
        ve_adjustment_low=14,
        ve_adjustment_mid=20,
        ve_adjustment_high=25,
        idle_rpm_target=950,
        timing_advance_idle=4,
    ),
    
    # Andrews Cams
    "ANDREWS_TW26": CamProfile(
        manufacturer="Andrews",
        model="TW-26",
        intake_lift=0.500,
        intake_duration=218,
        intake_open_btdc=16,
        intake_close_abdc=42,
        exhaust_lift=0.480,
        exhaust_duration=224,
        exhaust_open_bbdc=50,
        exhaust_close_atdc=14,
        overlap=30,
        category=CamCategory.MILD,
        ve_adjustment_low=8,
        ve_adjustment_mid=12,
        ve_adjustment_high=15,
        idle_rpm_target=875,
        timing_advance_idle=3,
    ),
    
    "ANDREWS_TW37": CamProfile(
        manufacturer="Andrews",
        model="TW-37",
        intake_lift=0.540,
        intake_duration=236,
        intake_open_btdc=26,
        intake_close_abdc=50,
        exhaust_lift=0.520,
        exhaust_duration=244,
        exhaust_open_bbdc=62,
        exhaust_close_atdc=22,
        overlap=48,
        category=CamCategory.AGGRESSIVE,
        ve_adjustment_low=18,
        ve_adjustment_mid=25,
        ve_adjustment_high=32,
        idle_rpm_target=975,
        timing_advance_idle=5,
    ),
}
```

### Additional Modification Factors

```python
# Mod stack adjustments (additive to cam base)
MOD_ADJUSTMENTS = {
    "air_cleaner": {
        "stock": {"low": 0, "mid": 0, "high": 0},
        "high_flow": {"low": 2, "mid": 4, "high": 5},
        "velocity_stack": {"low": 3, "mid": 6, "high": 8},
    },
    "exhaust": {
        "stock": {"low": 0, "mid": 0, "high": 0},
        "slip_on": {"low": 2, "mid": 3, "high": 4},
        "full_system_2into1": {"low": 4, "mid": 6, "high": 8},
        "full_system_2into2": {"low": 3, "mid": 5, "high": 7},
        "true_duals": {"low": 5, "mid": 7, "high": 10},
    },
    "displacement": {
        "stock": {"low": 0, "mid": 0, "high": 0},
        "107ci": {"low": 3, "mid": 4, "high": 5},
        "110ci": {"low": 5, "mid": 6, "high": 8},
        "117ci": {"low": 7, "mid": 9, "high": 12},
        "124ci": {"low": 10, "mid": 13, "high": 16},
        "128ci": {"low": 12, "mid": 16, "high": 20},
    },
    "heads": {
        "stock": {"low": 0, "mid": 0, "high": 0},
        "ported_stock": {"low": 2, "mid": 3, "high": 4},
        "cnc_ported": {"low": 4, "mid": 6, "high": 8},
        "aftermarket_flow": {"low": 5, "mid": 8, "high": 10},
    },
    "compression": {
        "stock_9.5": {"low": 0, "mid": 0, "high": 0},
        "10.5": {"low": 2, "mid": 2, "high": 3},
        "11.0": {"low": 3, "mid": 3, "high": 4},
        "12.0": {"low": 4, "mid": 5, "high": 6},
    },
}
```

---

## Pattern Matching Algorithm

### Exact Match

```python
def find_exact_cam_match(
    manufacturer: str,
    model: str,
    part_number: Optional[str] = None
) -> Optional[CamProfile]:
    """
    Find exact cam match in database.
    
    Args:
        manufacturer: Cam manufacturer name
        model: Cam model name
        part_number: Optional part number for disambiguation
    
    Returns:
        CamProfile if found, None otherwise
    """
    # Normalize input
    manufacturer_lower = manufacturer.lower().strip()
    model_lower = model.lower().strip()
    
    for key, profile in CAM_DATABASE.items():
        if (profile.manufacturer.lower() == manufacturer_lower and
            profile.model.lower() == model_lower):
            
            # If part number provided, verify match
            if part_number and profile.part_number:
                if profile.part_number.lower() != part_number.lower():
                    continue
            
            return profile
    
    return None
```

### Specification-Based Interpolation

For unknown cams, interpolate from specs:

```python
def interpolate_cam_profile(
    intake_lift: float,
    intake_duration: float,
    exhaust_lift: float,
    exhaust_duration: float,
    overlap: Optional[float] = None
) -> CamProfile:
    """
    Create interpolated cam profile from specifications.
    
    Uses known cam database to estimate VE adjustments
    based on provided specs.
    """
    # Calculate overlap if not provided
    if overlap is None:
        # Estimate based on duration (rough approximation)
        overlap = (intake_duration + exhaust_duration) / 2 - 200
    
    # Find nearest known cams by overlap
    known_cams = list(CAM_DATABASE.values())
    known_cams.sort(key=lambda c: abs(c.overlap - overlap) if c.overlap else 999)
    
    # Take weighted average of 3 nearest cams
    nearest = known_cams[:3]
    weights = [1.0 / (abs(c.overlap - overlap) + 1) for c in nearest]
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    
    # Interpolate VE adjustments
    ve_low = sum(c.ve_adjustment_low * w for c, w in zip(nearest, weights))
    ve_mid = sum(c.ve_adjustment_mid * w for c, w in zip(nearest, weights))
    ve_high = sum(c.ve_adjustment_high * w for c, w in zip(nearest, weights))
    idle_rpm = int(sum(c.idle_rpm_target * w for c, w in zip(nearest, weights)))
    timing_adj = sum(c.timing_advance_idle * w for c, w in zip(nearest, weights))
    
    # Determine category based on overlap
    if overlap < 15:
        category = CamCategory.STOCK
    elif overlap < 30:
        category = CamCategory.MILD
    elif overlap < 45:
        category = CamCategory.MODERATE
    elif overlap < 60:
        category = CamCategory.AGGRESSIVE
    else:
        category = CamCategory.RACE
    
    return CamProfile(
        manufacturer="Unknown",
        model=f"Custom ({intake_lift:.3f}/{exhaust_lift:.3f} lift)",
        intake_lift=intake_lift,
        intake_duration=intake_duration,
        intake_open_btdc=0,  # Unknown
        intake_close_abdc=0,
        exhaust_lift=exhaust_lift,
        exhaust_duration=exhaust_duration,
        exhaust_open_bbdc=0,
        exhaust_close_atdc=0,
        overlap=overlap,
        category=category,
        ve_adjustment_low=ve_low,
        ve_adjustment_mid=ve_mid,
        ve_adjustment_high=ve_high,
        idle_rpm_target=idle_rpm,
        timing_advance_idle=timing_adj,
    )
```

---

## VE Map Generation

### Core Generation Logic

```python
import numpy as np
from typing import Tuple

# Standard grid definitions
RPM_BINS = [800, 1000, 1200, 1500, 1750, 2000, 2250, 2500, 2750, 
            3000, 3250, 3500, 3750, 4000, 4250, 4500, 4750, 5000,
            5250, 5500, 5750, 6000, 6250, 6500]

KPA_BINS = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 
            85, 90, 95, 100, 105, 110]


def generate_cam_baseline_ve(
    cam_profile: CamProfile,
    mod_stack: dict,
    base_ve_table: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, dict]:
    """
    Generate cam-specific baseline VE tables.
    
    Args:
        cam_profile: Matched or interpolated cam profile
        mod_stack: Dict of modification selections
        base_ve_table: Stock VE table to adjust from
    
    Returns:
        Tuple of (front_ve, rear_ve, confidence_map)
    """
    # Calculate total adjustments per region
    adjustments = {
        "low": cam_profile.ve_adjustment_low,
        "mid": cam_profile.ve_adjustment_mid,
        "high": cam_profile.ve_adjustment_high,
    }
    
    # Add mod stack adjustments
    for mod_type, selection in mod_stack.items():
        if mod_type in MOD_ADJUSTMENTS and selection in MOD_ADJUSTMENTS[mod_type]:
            mod_adj = MOD_ADJUSTMENTS[mod_type][selection]
            adjustments["low"] += mod_adj["low"]
            adjustments["mid"] += mod_adj["mid"]
            adjustments["high"] += mod_adj["high"]
    
    # Generate VE adjustment map
    ve_adjustment = np.zeros_like(base_ve_table)
    confidence = np.zeros_like(base_ve_table)
    
    for i, rpm in enumerate(RPM_BINS):
        for j, kpa in enumerate(KPA_BINS):
            # Determine RPM region
            if rpm < 2500:
                region = "low"
                base_conf = 0.85  # Lower confidence at idle/low RPM
            elif rpm < 4000:
                region = "mid"
                base_conf = 0.90
            else:
                region = "high"
                base_conf = 0.85  # Slightly lower at high RPM
            
            # Get adjustment percentage
            adj_pct = adjustments[region] / 100.0
            
            # Apply load-based scaling
            # Higher load = more adjustment needed
            load_factor = kpa / 100.0
            
            # Low-load (vacuum) cells need less adjustment
            if kpa < 40:
                load_factor *= 0.5
            elif kpa < 60:
                load_factor *= 0.75
            
            # Calculate final adjustment
            ve_adjustment[i, j] = adj_pct * load_factor
            
            # Confidence based on data quality for this cam
            if cam_profile.manufacturer == "Unknown":
                confidence[i, j] = base_conf * 0.7  # Lower for interpolated
            else:
                confidence[i, j] = base_conf
    
    # Apply adjustments to base table
    front_ve = base_ve_table * (1.0 + ve_adjustment)
    
    # Rear cylinder runs hotter, needs slightly more fuel
    rear_adjustment = 0.02  # 2% richer baseline for rear
    rear_ve = front_ve * (1.0 + rear_adjustment)
    
    # Apply overlap compensation for idle cells
    if cam_profile.overlap and cam_profile.overlap > 30:
        overlap_comp = apply_overlap_compensation(
            front_ve, rear_ve, cam_profile, RPM_BINS, KPA_BINS
        )
        front_ve = overlap_comp[0]
        rear_ve = overlap_comp[1]
    
    confidence_map = {
        "map": confidence,
        "avg_confidence": float(np.mean(confidence)),
        "low_confidence_cells": int(np.sum(confidence < 0.7)),
    }
    
    return front_ve, rear_ve, confidence_map


def apply_overlap_compensation(
    front_ve: np.ndarray,
    rear_ve: np.ndarray,
    cam_profile: CamProfile,
    rpm_bins: list,
    kpa_bins: list
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply special compensation for high-overlap cams at idle/low-load.
    
    High-overlap cams have poor idle VE due to intake/exhaust overlap
    allowing reversion and dilution. This requires extra fuel to 
    maintain combustion stability.
    """
    # Overlap compensation factor (higher overlap = more compensation)
    overlap_factor = (cam_profile.overlap - 30) / 30.0  # Normalize 30-60° range
    overlap_factor = np.clip(overlap_factor, 0, 1)
    
    for i, rpm in enumerate(rpm_bins):
        for j, kpa in enumerate(kpa_bins):
            # Only apply to idle/low-load cells
            if rpm > 2000 or kpa > 50:
                continue
            
            # Higher compensation at lower RPM and lower load
            rpm_factor = 1.0 - (rpm - 800) / 1200  # Max at 800 RPM
            load_factor = 1.0 - (kpa - 20) / 30    # Max at 20 kPa
            
            # Combined compensation (up to +15% at worst case)
            compensation = 0.15 * overlap_factor * rpm_factor * load_factor
            
            front_ve[i, j] *= (1.0 + compensation)
            rear_ve[i, j] *= (1.0 + compensation)
    
    return front_ve, rear_ve
```

---

## Output Files

### Primary Outputs

| File | Description |
|------|-------------|
| `Cam_Baseline_VE_Front.csv` | Front cylinder VE baseline |
| `Cam_Baseline_VE_Rear.csv` | Rear cylinder VE baseline |
| `Cam_Profile_Report.json` | Profile match and adjustment details |
| `Cam_Tuning_Recommendations.txt` | Human-readable tuning guidance |

### Cam Profile Report Schema

```json
{
  "version": "1.0",
  "generated_at": "2025-12-06T14:30:00Z",
  "cam_profile": {
    "manufacturer": "S&S Cycle",
    "model": "585 Easy Start",
    "part_number": "330-0630",
    "category": "aggressive",
    "match_type": "exact",
    "specifications": {
      "intake_lift": 0.585,
      "intake_duration": 244,
      "exhaust_lift": 0.585,
      "exhaust_duration": 252,
      "overlap": 58
    }
  },
  "mod_stack": {
    "air_cleaner": "high_flow",
    "exhaust": "full_system_2into1",
    "displacement": "110ci",
    "heads": "cnc_ported",
    "compression": "10.5"
  },
  "adjustments_applied": {
    "low_rpm_pct": 28,
    "mid_rpm_pct": 42,
    "high_rpm_pct": 53,
    "breakdown": {
      "cam_base": {"low": 18, "mid": 28, "high": 35},
      "air_cleaner": {"low": 2, "mid": 4, "high": 5},
      "exhaust": {"low": 4, "mid": 6, "high": 8},
      "displacement": {"low": 5, "mid": 6, "high": 8},
      "heads": {"low": 4, "mid": 6, "high": 8},
      "compression": {"low": 2, "mid": 2, "high": 3}
    }
  },
  "confidence": {
    "overall": 0.87,
    "low_rpm_region": 0.82,
    "mid_rpm_region": 0.90,
    "high_rpm_region": 0.85,
    "low_confidence_cells": 12,
    "requires_verification": true
  },
  "recommendations": {
    "idle_rpm_target": 1000,
    "timing_advance_idle": 6,
    "afr_target_cruise": 13.5,
    "afr_target_wot": 12.8,
    "warnings": [
      "High-overlap cam will have rough idle - this is normal",
      "Expect 2-4 autotune cycles for final convergence",
      "Recommend knock monitoring for first WOT pulls"
    ]
  }
}
```

### Tuning Recommendations File

```text
================================================================================
                    CAM PROFILE TUNING RECOMMENDATIONS
                    Generated: 2025-12-06 14:30:00
================================================================================

CAM IDENTIFIED: S&S Cycle 585 Easy Start (#330-0630)
CATEGORY: Aggressive (high overlap)

MOD STACK DETECTED:
  • Air Cleaner: High-Flow Aftermarket
  • Exhaust: Full System 2-into-1
  • Displacement: 110ci
  • Heads: CNC Ported
  • Compression: 10.5:1

--------------------------------------------------------------------------------
                           VE ADJUSTMENT SUMMARY
--------------------------------------------------------------------------------

  RPM Range        Adjustment Applied    Confidence
  ─────────────    ──────────────────    ──────────
  800-2500 RPM     +28%                  82%
  2500-4000 RPM    +42%                  90%
  4000-6500 RPM    +53%                  85%

--------------------------------------------------------------------------------
                          TUNING RECOMMENDATIONS
--------------------------------------------------------------------------------

IDLE SETTINGS:
  • Target idle RPM: 1000 RPM (±50)
  • Idle timing advance: +6° from stock
  • Expect rough/lumpy idle - this is NORMAL for high-overlap cams

AFR TARGETS:
  • Cruise (light load): 13.5:1
  • Part throttle (moderate load): 13.2:1
  • WOT: 12.8:1

TIMING STRATEGY:
  • Start conservative: Stock timing - 2°
  • Advance in 1° increments while monitoring knock
  • Expected MBT: Stock + 4-6° at most RPM points
  • Watch 2500-3500 RPM range for knock sensitivity

EXPECTED BEHAVIOR:
  ✓ Strong mid-range pull starting around 2800 RPM
  ✓ Power peak shifted higher (5000-5500 RPM)
  ✓ Lumpy idle with slight vacuum fluctuation
  ✗ May surge at very light throttle (normal)
  ✗ Cold start may require slightly longer cranking

VERIFICATION PRIORITY:
  1. Low-RPM cells (1500-2500): Highest error potential
  2. High-load cells (90-100 kPa): Most critical for power
  3. Decel cells (0-40 kPa): May need enrichment for popping

--------------------------------------------------------------------------------
                              WARNINGS
--------------------------------------------------------------------------------

⚠️  HIGH-OVERLAP CAM: Idle quality will never match stock. The overlap 
    causes intake/exhaust gas mixing which reduces idle VE. The provided
    baseline compensates for this, but expect some "character" at idle.

⚠️  CONVERGENCE ESTIMATE: Plan for 2-4 autotune cycles to reach optimal
    calibration. This baseline gets you ~70-80% of the way there.

⚠️  KNOCK MONITORING: With 10.5:1 compression and aggressive timing,
    monitor knock closely on first WOT pulls. Have knock retard logging
    enabled.

================================================================================
                    Generated by DynoAI Cam Pattern Matcher v1.0
================================================================================
```

---

## CLI Interface

### New Flags

```bash
python ai_tuner_toolkit_dyno_v1_2.py \
  --generate-cam-baseline           # Enable cam baseline generation
  --cam-manufacturer "S&S Cycle"    # Cam manufacturer
  --cam-model "585 Easy Start"      # Cam model name
  --cam-part-number "330-0630"      # Optional part number
  # OR for custom/unknown cams:
  --cam-intake-lift 0.585           # Intake lift in inches
  --cam-intake-duration 244         # Intake duration at 0.053"
  --cam-exhaust-lift 0.585          # Exhaust lift
  --cam-exhaust-duration 252        # Exhaust duration
  --cam-overlap 58                  # Overlap degrees (optional)
  # Mod stack:
  --mod-air-cleaner "high_flow"     # Air cleaner type
  --mod-exhaust "full_system_2into1" # Exhaust type
  --mod-displacement "110ci"        # Engine displacement
  --mod-heads "cnc_ported"          # Head work
  --mod-compression "10.5"          # Compression ratio
  # Output:
  --base-ve tables/VE_Stock.csv     # Stock VE table to adjust from
  --outdir ./output                 # Output directory
```

### Interactive Mode

```bash
python ai_tuner_toolkit_dyno_v1_2.py --cam-wizard

# Launches interactive questionnaire:
# 1. Select cam manufacturer or enter "Custom"
# 2. Select model from filtered list or enter specs
# 3. Select each mod from dropdown
# 4. Confirm and generate
```

---

## Integration Points

### With Main Pipeline

```python
# In ai_tuner_toolkit_dyno_v1_2.py main()

if args.generate_cam_baseline:
    # Find or create cam profile
    if args.cam_manufacturer and args.cam_model:
        cam = find_exact_cam_match(
            args.cam_manufacturer, 
            args.cam_model,
            args.cam_part_number
        )
        if not cam:
            print(f"Warning: Cam not in database, interpolating from specs")
            cam = interpolate_cam_profile(
                args.cam_intake_lift or 0.5,
                args.cam_intake_duration or 220,
                args.cam_exhaust_lift or 0.5,
                args.cam_exhaust_duration or 226,
                args.cam_overlap
            )
    else:
        cam = interpolate_cam_profile(
            args.cam_intake_lift,
            args.cam_intake_duration,
            args.cam_exhaust_lift,
            args.cam_exhaust_duration,
            args.cam_overlap
        )
    
    # Build mod stack
    mod_stack = {
        "air_cleaner": args.mod_air_cleaner or "stock",
        "exhaust": args.mod_exhaust or "stock",
        "displacement": args.mod_displacement or "stock",
        "heads": args.mod_heads or "stock",
        "compression": args.mod_compression or "stock_9.5",
    }
    
    # Load base VE table
    base_ve = load_ve_table(args.base_ve)
    
    # Generate cam-specific baseline
    front_ve, rear_ve, confidence = generate_cam_baseline_ve(
        cam, mod_stack, base_ve
    )
    
    # Write outputs
    write_ve_table(front_ve, outdir / 'Cam_Baseline_VE_Front.csv')
    write_ve_table(rear_ve, outdir / 'Cam_Baseline_VE_Rear.csv')
    write_cam_report(cam, mod_stack, confidence, outdir / 'Cam_Profile_Report.json')
    write_tuning_recommendations(cam, mod_stack, outdir / 'Cam_Tuning_Recommendations.txt')
```

### With Subsequent Analysis

The cam baseline becomes the starting point for standard analysis:

```bash
# Step 1: Generate cam baseline
python ai_tuner_toolkit_dyno_v1_2.py \
  --generate-cam-baseline \
  --cam-manufacturer "S&S Cycle" --cam-model "585" \
  --mod-exhaust "full_system_2into1" \
  --base-ve tables/VE_Stock.csv \
  --outdir ./baseline

# Step 2: Use cam baseline for dyno analysis
python ai_tuner_toolkit_dyno_v1_2.py \
  --csv dyno_log.csv \
  --base_front ./baseline/Cam_Baseline_VE_Front.csv \
  --base_rear ./baseline/Cam_Baseline_VE_Rear.csv \
  --outdir ./tuned
```

---

## Safety Considerations

### Adjustment Limits
- Maximum VE adjustment: **+60%** (prevents unreasonable values)
- Minimum VE adjustment: **-10%** (cams rarely reduce VE)
- Confidence threshold for auto-apply: **>75%**

### Conservative Bias
- All adjustments biased **2-3% rich** for safety
- Timing recommendations are **conservative** (advance from stock, not MBT)
- High-overlap compensation is **generous** (better to be rich at idle)

### Required Warnings
- All outputs marked as "BASELINE - REQUIRES VERIFICATION"
- Low-confidence cells flagged for manual review
- Knock monitoring recommendation included for all aggressive cams

---

## Testing Requirements

### Unit Tests

```python
# tests/unit/test_cam_pattern_matching.py

def test_exact_cam_match():
    """Known cam matched from database."""
    
def test_cam_not_found_returns_none():
    """Unknown cam returns None for exact match."""
    
def test_interpolation_moderate_overlap():
    """Moderate overlap cam interpolated correctly."""
    
def test_mod_stack_additive():
    """Mod adjustments add to cam base correctly."""
    
def test_overlap_compensation_applied():
    """High-overlap cams get idle compensation."""
    
def test_adjustment_limits_enforced():
    """Extreme adjustments clamped to safe range."""
```

### Integration Tests

```python
# tests/integration/test_cam_baseline_pipeline.py

def test_full_cam_baseline_generation():
    """Full pipeline produces VE tables and reports."""
    
def test_cam_baseline_used_in_analysis():
    """Cam baseline integrates with standard analysis."""
    
def test_confidence_map_generated():
    """Confidence scores calculated and reported."""
```

### Accuracy Testing

Compare generated baselines against known-good tunes:
- Collect tuned VE tables from community (anonymized)
- Calculate delta between DynoAI baseline and final tune
- Target: <15% average delta from final tune

---

## Implementation Phases

### Phase 1: Database & Matching (Week 1-2)
- [ ] Implement cam profile database (20+ popular cams)
- [ ] Implement exact match lookup
- [ ] Implement specification-based interpolation
- [ ] Add mod stack adjustment system

### Phase 2: VE Generation (Week 2-3)
- [ ] Implement `generate_cam_baseline_ve()` function
- [ ] Implement `apply_overlap_compensation()` function
- [ ] Create confidence scoring system
- [ ] Generate human-readable recommendations

### Phase 3: Integration & CLI (Week 3-4)
- [ ] Add CLI flags for cam baseline generation
- [ ] Create interactive wizard mode
- [ ] Integrate with existing analysis pipeline
- [ ] Write output generators (CSV, JSON, TXT)

### Phase 4: Testing & Validation (Week 4-5)
- [ ] Write unit tests (target: 90% coverage)
- [ ] Collect validation data from community
- [ ] Tune interpolation weights based on validation
- [ ] Update documentation

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Database coverage | 25+ popular cams in initial release |
| Baseline accuracy | <15% average delta from final tune |
| Time savings | 50-70% reduction in autotune cycles |
| User adoption | >60% of Stage 2+ users within 6 months |

---

## Future Enhancements

### Phase 2 Additions
- Machine learning model trained on community tunes
- Automatic cam detection from dyno log characteristics
- Integration with manufacturer APIs for spec lookup

### Community Contributions
- Allow users to submit validated cam profiles
- Crowdsource accuracy data for database refinement
- Public leaderboard for most accurate predictions

---

## References

- [VTWIN_TUNING_TECHNICAL_VALIDATION.md](../VTWIN_TUNING_TECHNICAL_VALIDATION.md) - Source research
- [DYNOAI_SAFETY_RULES.md](../DYNOAI_SAFETY_RULES.md) - Safety limits
- S&S Cycle cam specification sheets
- Wood Performance cam catalog
- Feuling Parts cam specifications
- Community tuning forums (HDForums, V-Twin Forum)

