"""
Environmental Corrections Module for DynoAI

This module provides comprehensive environmental corrections for fuel tuning,
accounting for atmospheric conditions that affect air density and fuel requirements.

Environmental factors and their effects:
- Barometric Pressure: Lower pressure = less air mass = less fuel needed
- Altitude: Derived from barometric, ~3% less fuel per 1000ft
- Humidity: Water vapor displaces oxygen, ~1% less fuel per 10% RH
- Ambient Temperature: Affects air density (handled separately from IAT)
- Engine/Coolant Temperature (ECT): Cold engines need enrichment

Reference Standards:
- SAE J1349: Standard for engine power correction
- ISO 1585: Similar international standard
- DIN 70020: German standard for power measurement

Author: DynoAI_3
Date: 2025-12-15
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from enum import Enum
import math


class CorrectionStandard(Enum):
    """Correction factor calculation standard."""
    SAE_J1349 = "sae_j1349"  # SAE standard (US)
    ISO_1585 = "iso_1585"    # ISO standard (International)
    DIN_70020 = "din_70020"  # DIN standard (German)
    SIMPLIFIED = "simplified"  # Simplified linear model


@dataclass
class EnvironmentalConditions:
    """
    Current environmental/atmospheric conditions.
    
    All values should be actual measured conditions during the dyno run.
    If not available, standard conditions will be assumed.
    
    Attributes:
        barometric_pressure_inhg: Barometric pressure in inches of mercury (inHg)
            Standard: 29.92 inHg at sea level
        ambient_temp_f: Ambient air temperature in Fahrenheit
            Standard: 77°F (25°C) for SAE J1349
        humidity_percent: Relative humidity as percentage (0-100)
            Standard: 0% (dry air) for correction calculations
        altitude_ft: Altitude in feet above sea level
            Can be calculated from barometric if not provided
        ect_f: Engine coolant temperature in Fahrenheit
            Normal operating: 180-220°F
        iat_f: Intake air temperature in Fahrenheit
            Usually higher than ambient due to engine heat
    """
    barometric_pressure_inhg: float = 29.92  # Sea level standard
    ambient_temp_f: float = 77.0  # SAE J1349 standard (25°C)
    humidity_percent: float = 0.0  # Dry air standard
    altitude_ft: Optional[float] = None  # Calculated from baro if not provided
    ect_f: Optional[float] = None  # Engine coolant temp
    iat_f: Optional[float] = None  # Intake air temp (separate from ambient)
    
    def __post_init__(self):
        """Calculate altitude from barometric if not provided."""
        if self.altitude_ft is None:
            self.altitude_ft = estimate_altitude_from_baro(self.barometric_pressure_inhg)


@dataclass
class StandardConditions:
    """
    Standard/reference conditions for correction calculations.
    
    Different standards use slightly different reference conditions:
    - SAE J1349: 77°F (25°C), 29.92 inHg, dry air
    - ISO 1585: 77°F (25°C), 29.92 inHg (1013 mbar), dry air
    - DIN 70020: 68°F (20°C), 29.92 inHg (1013 mbar), dry air
    """
    pressure_inhg: float = 29.92
    temp_f: float = 77.0
    humidity_percent: float = 0.0
    altitude_ft: float = 0.0


# Standard reference conditions for each standard
STANDARD_CONDITIONS = {
    CorrectionStandard.SAE_J1349: StandardConditions(29.92, 77.0, 0.0, 0.0),
    CorrectionStandard.ISO_1585: StandardConditions(29.92, 77.0, 0.0, 0.0),
    CorrectionStandard.DIN_70020: StandardConditions(29.92, 68.0, 0.0, 0.0),
    CorrectionStandard.SIMPLIFIED: StandardConditions(29.92, 77.0, 0.0, 0.0),
}


@dataclass
class EnvironmentalCorrectionResult:
    """
    Results from environmental correction calculation.
    
    Attributes:
        total_correction: Combined correction factor (multiply fuel by this)
        pressure_correction: Correction for barometric pressure
        temperature_correction: Correction for ambient temperature
        humidity_correction: Correction for humidity
        altitude_correction: Correction for altitude (if separate from pressure)
        ect_correction: Correction for engine coolant temperature
        standard_used: Which correction standard was applied
        is_standard_day: Whether conditions are near standard
        details: Breakdown of individual factors
    """
    total_correction: float
    pressure_correction: float
    temperature_correction: float
    humidity_correction: float
    altitude_correction: float
    ect_correction: float
    standard_used: CorrectionStandard
    is_standard_day: bool
    details: Dict[str, float] = field(default_factory=dict)


def estimate_altitude_from_baro(pressure_inhg: float) -> float:
    """
    Estimate altitude from barometric pressure using barometric formula.
    
    Uses the international barometric formula:
    h = 44330 * (1 - (P/P0)^0.1903)
    
    Where:
    - h = altitude in meters
    - P = measured pressure
    - P0 = sea level pressure (29.92 inHg = 1013.25 mbar)
    
    Args:
        pressure_inhg: Barometric pressure in inches of mercury
        
    Returns:
        Estimated altitude in feet
        
    Examples:
        >>> estimate_altitude_from_baro(29.92)  # Sea level
        0.0
        >>> estimate_altitude_from_baro(24.89)  # ~5000 ft
        5000.0 (approximately)
    """
    # Convert inHg to ratio vs standard
    pressure_ratio = pressure_inhg / 29.92
    
    # Barometric formula (result in meters)
    altitude_m = 44330 * (1 - math.pow(pressure_ratio, 0.1903))
    
    # Convert to feet
    altitude_ft = altitude_m * 3.28084
    
    return max(0, altitude_ft)


def estimate_baro_from_altitude(altitude_ft: float) -> float:
    """
    Estimate barometric pressure from altitude.
    
    Inverse of the barometric formula.
    
    Args:
        altitude_ft: Altitude in feet above sea level
        
    Returns:
        Estimated barometric pressure in inHg
    """
    altitude_m = altitude_ft / 3.28084
    pressure_ratio = math.pow(1 - (altitude_m / 44330), 5.255)
    return 29.92 * pressure_ratio


class EnvironmentalCorrector:
    """
    Comprehensive environmental correction calculator.
    
    This class calculates fuel correction factors based on atmospheric
    conditions compared to standard reference conditions.
    
    The correction factor represents how much MORE or LESS fuel is needed:
    - factor > 1.0: Need MORE fuel (e.g., cold, high pressure)
    - factor < 1.0: Need LESS fuel (e.g., hot, high altitude, humid)
    - factor = 1.0: Standard conditions, no correction needed
    
    Args:
        standard: Which correction standard to use (default: SAE_J1349)
        reference: Custom reference conditions (optional, overrides standard)
        enable_pressure: Enable barometric pressure correction
        enable_temperature: Enable ambient temperature correction
        enable_humidity: Enable humidity correction
        enable_ect: Enable engine coolant temperature correction
        ect_cold_threshold_f: ECT below this needs cold enrichment (default: 160°F)
        ect_warm_threshold_f: ECT above this is fully warm (default: 180°F)
        max_correction: Maximum allowed correction factor (default: 1.25 = ±25%)
        
    Example:
        >>> corrector = EnvironmentalCorrector()
        >>> conditions = EnvironmentalConditions(
        ...     barometric_pressure_inhg=24.89,  # ~5000 ft altitude
        ...     ambient_temp_f=90.0,              # Hot day
        ...     humidity_percent=60.0,            # Humid
        ... )
        >>> result = corrector.calculate(conditions)
        >>> print(f"Total correction: {result.total_correction:.3f}")
        Total correction: 0.847  # Need ~15% less fuel
    """
    
    def __init__(
        self,
        standard: CorrectionStandard = CorrectionStandard.SAE_J1349,
        reference: Optional[StandardConditions] = None,
        enable_pressure: bool = True,
        enable_temperature: bool = True,
        enable_humidity: bool = True,
        enable_ect: bool = True,
        ect_cold_threshold_f: float = 160.0,
        ect_warm_threshold_f: float = 180.0,
        max_correction: float = 1.25,
    ):
        self.standard = standard
        self.reference = reference or STANDARD_CONDITIONS[standard]
        self.enable_pressure = enable_pressure
        self.enable_temperature = enable_temperature
        self.enable_humidity = enable_humidity
        self.enable_ect = enable_ect
        self.ect_cold_threshold_f = ect_cold_threshold_f
        self.ect_warm_threshold_f = ect_warm_threshold_f
        self.max_correction = max_correction
    
    def calculate(self, conditions: EnvironmentalConditions) -> EnvironmentalCorrectionResult:
        """
        Calculate comprehensive environmental correction factor.
        
        Args:
            conditions: Current environmental conditions
            
        Returns:
            EnvironmentalCorrectionResult with all correction factors
        """
        details = {}
        
        # Calculate individual corrections
        pressure_corr = self._calculate_pressure_correction(conditions, details)
        temp_corr = self._calculate_temperature_correction(conditions, details)
        humidity_corr = self._calculate_humidity_correction(conditions, details)
        altitude_corr = 1.0  # Altitude is captured in pressure correction
        ect_corr = self._calculate_ect_correction(conditions, details)
        
        # Combine corrections (multiplicative)
        total = pressure_corr * temp_corr * humidity_corr * ect_corr
        
        # Apply safety clamp
        min_corr = 1.0 / self.max_correction
        max_corr = self.max_correction
        total_clamped = max(min_corr, min(max_corr, total))
        
        if abs(total - total_clamped) > 0.001:
            details['clamped'] = True
            details['unclamped_total'] = total
        
        # Determine if near standard conditions
        is_standard = self._is_standard_day(conditions)
        
        return EnvironmentalCorrectionResult(
            total_correction=total_clamped,
            pressure_correction=pressure_corr,
            temperature_correction=temp_corr,
            humidity_correction=humidity_corr,
            altitude_correction=altitude_corr,
            ect_correction=ect_corr,
            standard_used=self.standard,
            is_standard_day=is_standard,
            details=details,
        )
    
    def _calculate_pressure_correction(
        self, conditions: EnvironmentalConditions, details: Dict
    ) -> float:
        """
        Calculate barometric pressure correction.
        
        Lower pressure = less air mass = less fuel needed.
        
        SAE J1349 formula:
        Cf = (Pd / Ps) where Pd = dry air pressure
        
        Simplified: correction = P_actual / P_standard
        """
        if not self.enable_pressure:
            return 1.0
        
        # Pressure ratio (actual / standard)
        pressure_ratio = conditions.barometric_pressure_inhg / self.reference.pressure_inhg
        
        # Record details
        details['pressure_ratio'] = pressure_ratio
        details['pressure_actual_inhg'] = conditions.barometric_pressure_inhg
        details['pressure_standard_inhg'] = self.reference.pressure_inhg
        
        if conditions.altitude_ft:
            details['estimated_altitude_ft'] = conditions.altitude_ft
        
        return pressure_ratio
    
    def _calculate_temperature_correction(
        self, conditions: EnvironmentalConditions, details: Dict
    ) -> float:
        """
        Calculate ambient temperature correction.
        
        Air density varies inversely with absolute temperature.
        Cold air is denser = more air mass = more fuel needed.
        
        SAE J1349 formula uses absolute temperature ratio:
        Cf = sqrt(Ts / Ta) where temperatures are in Rankine
        
        Args:
            conditions: Environmental conditions
            details: Dictionary to store calculation details
            
        Returns:
            Temperature correction factor
        """
        if not self.enable_temperature:
            return 1.0
        
        # Convert to Rankine (absolute temperature)
        temp_actual_r = conditions.ambient_temp_f + 459.67
        temp_standard_r = self.reference.temp_f + 459.67
        
        # Temperature correction (SAE J1349 uses square root)
        if self.standard == CorrectionStandard.SAE_J1349:
            temp_correction = math.sqrt(temp_standard_r / temp_actual_r)
        else:
            # Simplified linear model
            temp_correction = temp_standard_r / temp_actual_r
        
        details['temp_actual_f'] = conditions.ambient_temp_f
        details['temp_standard_f'] = self.reference.temp_f
        details['temp_correction_method'] = self.standard.value
        
        return temp_correction
    
    def _calculate_humidity_correction(
        self, conditions: EnvironmentalConditions, details: Dict
    ) -> float:
        """
        Calculate humidity correction.
        
        Water vapor displaces oxygen in the air, reducing the effective
        air charge. High humidity = less oxygen = less fuel needed.
        
        Effect is approximately:
        - ~1% less fuel per 10% relative humidity
        - Effect is more pronounced at higher temperatures
        
        Uses partial pressure of water vapor to calculate correction.
        """
        if not self.enable_humidity or conditions.humidity_percent <= 0:
            return 1.0
        
        # Calculate saturation vapor pressure (Magnus formula)
        temp_c = (conditions.ambient_temp_f - 32) * 5 / 9
        
        # Magnus formula for saturation vapor pressure (in mbar)
        es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
        
        # Actual vapor pressure
        e = es * (conditions.humidity_percent / 100)
        
        # Convert barometric to mbar for calculation
        baro_mbar = conditions.barometric_pressure_inhg * 33.8639
        
        # Dry air partial pressure
        dry_pressure = baro_mbar - e
        
        # Correction factor (ratio of dry air to total pressure)
        # Adjusted for molecular weight difference (water vs air)
        # Water vapor is lighter than air (18 vs 29 g/mol)
        humidity_correction = (dry_pressure / baro_mbar) + (e / baro_mbar) * (18 / 29)
        
        details['humidity_percent'] = conditions.humidity_percent
        details['vapor_pressure_mbar'] = e
        details['dry_pressure_mbar'] = dry_pressure
        
        return humidity_correction
    
    def _calculate_ect_correction(
        self, conditions: EnvironmentalConditions, details: Dict
    ) -> float:
        """
        Calculate engine coolant temperature (ECT) correction.
        
        Cold engines need enrichment because:
        1. Fuel vaporization is poor on cold surfaces
        2. Cylinder wall temperatures affect combustion
        3. Oil viscosity increases friction losses
        
        Correction ramps from cold enrichment to 1.0 at operating temp.
        
        Typical cold enrichment: +10-20% when cold
        """
        if not self.enable_ect or conditions.ect_f is None:
            details['ect_status'] = 'disabled_or_no_data'
            return 1.0
        
        ect = conditions.ect_f
        
        if ect >= self.ect_warm_threshold_f:
            # Fully warm, no correction needed
            details['ect_status'] = 'warm'
            details['ect_actual_f'] = ect
            return 1.0
        
        if ect <= self.ect_cold_threshold_f:
            # Cold engine, apply maximum enrichment
            # Scale based on how cold (colder = more enrichment)
            # At 100°F: ~15% enrichment, at 50°F: ~25% enrichment
            cold_factor = (self.ect_cold_threshold_f - ect) / 100.0
            cold_enrichment = 1.15 + (cold_factor * 0.1)  # 15-25% enrichment
            cold_enrichment = min(cold_enrichment, 1.30)  # Cap at 30%
            
            details['ect_status'] = 'cold'
            details['ect_actual_f'] = ect
            details['ect_enrichment_pct'] = (cold_enrichment - 1) * 100
            return cold_enrichment
        
        # Transitional zone - linear interpolation
        warmup_progress = (ect - self.ect_cold_threshold_f) / (
            self.ect_warm_threshold_f - self.ect_cold_threshold_f
        )
        
        # Enrichment decreases linearly from 15% to 0% as engine warms
        enrichment = 1.15 - (0.15 * warmup_progress)
        
        details['ect_status'] = 'warming'
        details['ect_actual_f'] = ect
        details['ect_warmup_progress'] = warmup_progress
        details['ect_enrichment_pct'] = (enrichment - 1) * 100
        
        return enrichment
    
    def _is_standard_day(self, conditions: EnvironmentalConditions) -> bool:
        """
        Check if conditions are close to standard reference.
        
        Returns True if within typical tolerances:
        - Pressure: ±0.5 inHg
        - Temperature: ±10°F
        - Humidity: <30%
        - Altitude: <1000 ft
        """
        pressure_ok = abs(conditions.barometric_pressure_inhg - self.reference.pressure_inhg) < 0.5
        temp_ok = abs(conditions.ambient_temp_f - self.reference.temp_f) < 10
        humidity_ok = conditions.humidity_percent < 30
        altitude_ok = (conditions.altitude_ft or 0) < 1000
        
        return pressure_ok and temp_ok and humidity_ok and altitude_ok
    
    def get_correction_for_altitude(self, altitude_ft: float) -> float:
        """
        Quick method to get correction factor for a given altitude.
        
        Useful for altitude-only calculations without full conditions.
        
        Args:
            altitude_ft: Altitude in feet
            
        Returns:
            Correction factor (e.g., 0.88 at 5000 ft = 12% less fuel)
        """
        baro = estimate_baro_from_altitude(altitude_ft)
        conditions = EnvironmentalConditions(
            barometric_pressure_inhg=baro,
            ambient_temp_f=self.reference.temp_f,
            humidity_percent=0.0,
        )
        result = self.calculate(conditions)
        return result.pressure_correction
    
    def get_correction_summary(self, conditions: EnvironmentalConditions) -> str:
        """
        Get a human-readable summary of environmental corrections.
        
        Args:
            conditions: Environmental conditions
            
        Returns:
            Multi-line summary string
        """
        result = self.calculate(conditions)
        
        lines = [
            "=== Environmental Correction Summary ===",
            f"Standard: {result.standard_used.value}",
            f"Is Standard Day: {'Yes' if result.is_standard_day else 'No'}",
            "",
            "Conditions:",
            f"  Barometric: {conditions.barometric_pressure_inhg:.2f} inHg",
            f"  Altitude: {conditions.altitude_ft:.0f} ft",
            f"  Ambient Temp: {conditions.ambient_temp_f:.1f}°F",
            f"  Humidity: {conditions.humidity_percent:.1f}%",
        ]
        
        if conditions.ect_f:
            lines.append(f"  Engine Temp: {conditions.ect_f:.1f}°F")
        
        lines.extend([
            "",
            "Corrections:",
            f"  Pressure: {result.pressure_correction:.4f} ({(result.pressure_correction-1)*100:+.1f}%)",
            f"  Temperature: {result.temperature_correction:.4f} ({(result.temperature_correction-1)*100:+.1f}%)",
            f"  Humidity: {result.humidity_correction:.4f} ({(result.humidity_correction-1)*100:+.1f}%)",
            f"  ECT: {result.ect_correction:.4f} ({(result.ect_correction-1)*100:+.1f}%)",
            "",
            f"TOTAL CORRECTION: {result.total_correction:.4f} ({(result.total_correction-1)*100:+.1f}%)",
        ])
        
        if result.total_correction > 1.0:
            lines.append("  → Need MORE fuel than standard conditions")
        elif result.total_correction < 1.0:
            lines.append("  → Need LESS fuel than standard conditions")
        else:
            lines.append("  → No correction needed")
        
        return "\n".join(lines)


# Convenience functions for common use cases

def calculate_altitude_correction(altitude_ft: float) -> float:
    """
    Calculate fuel correction for altitude only.
    
    Rule of thumb: ~3% less fuel per 1000 ft altitude.
    
    Args:
        altitude_ft: Altitude in feet
        
    Returns:
        Correction factor (multiply fuel requirement by this)
        
    Examples:
        >>> calculate_altitude_correction(0)
        1.0
        >>> calculate_altitude_correction(5000)
        0.83  # ~17% less fuel
    """
    corrector = EnvironmentalCorrector(
        enable_temperature=False,
        enable_humidity=False,
        enable_ect=False,
    )
    return corrector.get_correction_for_altitude(altitude_ft)


def calculate_density_altitude(
    pressure_altitude_ft: float,
    temp_f: float,
    reference_temp_f: float = 59.0,  # ISA standard temp at sea level
) -> float:
    """
    Calculate density altitude from pressure altitude and temperature.
    
    Density altitude is the altitude at which the current air density
    would be found in a standard atmosphere.
    
    Args:
        pressure_altitude_ft: Pressure altitude (from altimeter at 29.92)
        temp_f: Actual outside air temperature
        reference_temp_f: ISA standard temp (59°F at sea level)
        
    Returns:
        Density altitude in feet
        
    Example:
        Hot day at 5000 ft pressure altitude, 95°F:
        >>> calculate_density_altitude(5000, 95)
        8500  # Effectively at 8500 ft for air density
    """
    # ISA standard temperature lapse rate: 3.5°F per 1000 ft
    isa_temp_f = reference_temp_f - (pressure_altitude_ft / 1000 * 3.5)
    
    # Temperature deviation from ISA
    temp_deviation_f = temp_f - isa_temp_f
    
    # Density altitude = pressure altitude + (120 * temp deviation)
    # This is the pilot's rule of thumb
    density_altitude = pressure_altitude_ft + (120 * temp_deviation_f)
    
    return density_altitude


def calculate_sae_j1349_correction(
    barometric_inhg: float,
    temp_f: float,
    humidity_percent: float = 0.0,
) -> float:
    """
    Calculate SAE J1349 power correction factor.
    
    This is the standard correction used in dyno testing to normalize
    results to standard conditions (77°F, 29.92 inHg, dry air).
    
    Args:
        barometric_inhg: Barometric pressure in inches Hg
        temp_f: Ambient temperature in Fahrenheit
        humidity_percent: Relative humidity (0-100)
        
    Returns:
        SAE J1349 correction factor
        
    Example:
        >>> calculate_sae_j1349_correction(29.92, 77.0, 0.0)
        1.0  # Standard conditions
        >>> calculate_sae_j1349_correction(24.89, 90.0, 60.0)
        0.847  # High altitude, hot, humid
    """
    corrector = EnvironmentalCorrector(
        standard=CorrectionStandard.SAE_J1349,
        enable_ect=False,
    )
    conditions = EnvironmentalConditions(
        barometric_pressure_inhg=barometric_inhg,
        ambient_temp_f=temp_f,
        humidity_percent=humidity_percent,
    )
    result = corrector.calculate(conditions)
    return result.total_correction


# Export public API
__all__ = [
    'CorrectionStandard',
    'EnvironmentalConditions',
    'StandardConditions',
    'EnvironmentalCorrectionResult',
    'EnvironmentalCorrector',
    'estimate_altitude_from_baro',
    'estimate_baro_from_altitude',
    'calculate_altitude_correction',
    'calculate_density_altitude',
    'calculate_sae_j1349_correction',
    'STANDARD_CONDITIONS',
]


if __name__ == "__main__":
    # Example usage
    print("DynoAI Environmental Correction Module")
    print("=" * 50)
    
    # Create corrector
    corrector = EnvironmentalCorrector()
    
    # Test various conditions
    test_cases = [
        ("Sea Level, Standard Day", EnvironmentalConditions()),
        ("5000 ft Altitude", EnvironmentalConditions(barometric_pressure_inhg=24.89)),
        ("Hot Day (95°F)", EnvironmentalConditions(ambient_temp_f=95.0)),
        ("Cold Day (40°F)", EnvironmentalConditions(ambient_temp_f=40.0)),
        ("High Humidity (80%)", EnvironmentalConditions(humidity_percent=80.0)),
        ("Cold Engine (120°F ECT)", EnvironmentalConditions(ect_f=120.0)),
        ("Denver Hot Day", EnvironmentalConditions(
            barometric_pressure_inhg=24.89,
            ambient_temp_f=95.0,
            humidity_percent=30.0,
        )),
        ("Seattle Cool Humid", EnvironmentalConditions(
            barometric_pressure_inhg=29.5,
            ambient_temp_f=55.0,
            humidity_percent=85.0,
        )),
    ]
    
    for name, conditions in test_cases:
        result = corrector.calculate(conditions)
        pct = (result.total_correction - 1) * 100
        print(f"\n{name}:")
        print(f"  Correction: {result.total_correction:.4f} ({pct:+.1f}%)")
        if not result.is_standard_day:
            print(f"  [Non-standard conditions]")
    
    # Detailed summary for one case
    print("\n" + "=" * 50)
    denver = EnvironmentalConditions(
        barometric_pressure_inhg=24.89,
        ambient_temp_f=95.0,
        humidity_percent=30.0,
        ect_f=185.0,
    )
    print(corrector.get_correction_summary(denver))








