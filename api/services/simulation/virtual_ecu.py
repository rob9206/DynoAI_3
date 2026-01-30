"""
Virtual ECU Simulator - Simulates ECU fuel delivery based on VE tables.

This module simulates how an ECU calculates fuel delivery:
1. Looks up VE from table (RPM x MAP)
2. Calculates air mass from MAP and displacement
3. Calculates required fuel for target AFR
4. Applies VE correction to fuel delivery

The key insight: When the ECU's VE table is wrong, the resulting AFR
will be wrong. This creates realistic tuning errors that must be corrected.

Example:
    - ECU thinks VE = 0.85 at 3000 RPM, 80 kPa
    - Actual VE = 0.95 (engine breathes better than ECU knows)
    - ECU delivers fuel for VE=0.85
    - Result: AFR is LEAN (actual air > expected air)
    - Tuning correction: Increase VE table to 0.95

This is the foundation for closed-loop virtual tuning!
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.interpolate import RegularGridInterpolator

logger = logging.getLogger(__name__)


# Standard DynoAI grid dimensions
DEFAULT_RPM_BINS = [1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500]
DEFAULT_MAP_BINS = [20, 30, 40, 50, 60, 70, 80, 90, 100]  # kPa

# Physical constants
STOICH_AFR = 14.7  # Stoichiometric AFR for gasoline
R_SPECIFIC_AIR = 287.05  # J/(kg·K) - specific gas constant for air
KELVIN_OFFSET = 273.15


@dataclass
class VirtualECU:
    """
    Simulates an ECU that reads VE tables and controls fueling.
    
    The ECU calculates injector pulse width based on:
    - VE table lookup (RPM x MAP)
    - Target AFR table
    - Air density corrections
    - Engine displacement and speed
    
    Attributes:
        ve_table_front: Front cylinder VE table (RPM x MAP grid)
        ve_table_rear: Rear cylinder VE table (RPM x MAP grid)
        afr_target_table: Target AFR table (RPM x MAP grid)
        rpm_bins: RPM axis for tables
        map_bins: MAP axis for tables (kPa)
        displacement_ci: Engine displacement per cylinder (cubic inches)
        num_cylinders: Number of cylinders (default: 2 for V-twin)
        ambient_temp_f: Ambient temperature (°F) for air density
        barometric_pressure_inhg: Barometric pressure (inHg)
    """
    
    # VE Tables (Front/Rear for V-twin)
    ve_table_front: np.ndarray
    ve_table_rear: np.ndarray
    
    # AFR Target Table
    afr_target_table: np.ndarray
    
    # Table axes
    rpm_bins: list[int] = field(default_factory=lambda: DEFAULT_RPM_BINS.copy())
    map_bins: list[int] = field(default_factory=lambda: DEFAULT_MAP_BINS.copy())
    
    # Engine specs
    displacement_ci: float = 114.0  # M8 114ci = 57ci per cylinder
    num_cylinders: int = 2
    
    # Environmental conditions
    ambient_temp_f: float = 75.0
    barometric_pressure_inhg: float = 29.92
    
    # Interpolators (built on init)
    _interp_ve_front: RegularGridInterpolator | None = field(default=None, init=False, repr=False)
    _interp_ve_rear: RegularGridInterpolator | None = field(default=None, init=False, repr=False)
    _interp_afr_target: RegularGridInterpolator | None = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """Build interpolators for fast table lookups."""
        # Validate table dimensions
        expected_shape = (len(self.rpm_bins), len(self.map_bins))
        
        if self.ve_table_front.shape != expected_shape:
            raise ValueError(
                f"ve_table_front shape {self.ve_table_front.shape} != expected {expected_shape}"
            )
        if self.ve_table_rear.shape != expected_shape:
            raise ValueError(
                f"ve_table_rear shape {self.ve_table_rear.shape} != expected {expected_shape}"
            )
        if self.afr_target_table.shape != expected_shape:
            raise ValueError(
                f"afr_target_table shape {self.afr_target_table.shape} != expected {expected_shape}"
            )
        
        # Build interpolators (linear interpolation, clamp to bounds)
        self._interp_ve_front = RegularGridInterpolator(
            (self.rpm_bins, self.map_bins),
            self.ve_table_front,
            method='linear',
            bounds_error=False,
            fill_value=None  # Extrapolate
        )
        
        self._interp_ve_rear = RegularGridInterpolator(
            (self.rpm_bins, self.map_bins),
            self.ve_table_rear,
            method='linear',
            bounds_error=False,
            fill_value=None
        )
        
        self._interp_afr_target = RegularGridInterpolator(
            (self.rpm_bins, self.map_bins),
            self.afr_target_table,
            method='linear',
            bounds_error=False,
            fill_value=None
        )
        
        logger.debug(
            f"VirtualECU initialized: {len(self.rpm_bins)}x{len(self.map_bins)} grid, "
            f"{self.displacement_ci}ci displacement"
        )
    
    def lookup_ve(self, rpm: float, map_kpa: float, cylinder: Literal['front', 'rear']) -> float:
        """
        Look up VE value from table at given RPM and MAP.
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
            cylinder: Which cylinder ('front' or 'rear')
        
        Returns:
            VE value (0.0 to ~1.5, typically 0.7-1.0)
        """
        interp = self._interp_ve_front if cylinder == 'front' else self._interp_ve_rear
        ve_value = float(interp([rpm, map_kpa])[0])
        
        # Clamp to reasonable range
        return np.clip(ve_value, 0.3, 1.5)
    
    def lookup_target_afr(self, rpm: float, map_kpa: float) -> float:
        """
        Look up target AFR from table at given RPM and MAP.
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
        
        Returns:
            Target AFR (typically 12.0-14.7)
        """
        afr = float(self._interp_afr_target([rpm, map_kpa])[0])
        
        # Clamp to reasonable range
        return np.clip(afr, 10.0, 18.0)
    
    def calculate_air_mass_mg(self, rpm: float, map_kpa: float) -> float:
        """
        Calculate theoretical air mass per combustion event.
        
        Uses ideal gas law: PV = mRT
        Solving for mass: m = PV / RT
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
        
        Returns:
            Air mass in milligrams per combustion event
        """
        # Cylinder displacement in cubic meters
        displacement_per_cyl_ci = self.displacement_ci / self.num_cylinders
        displacement_m3 = displacement_per_cyl_ci * 0.0000163871  # ci to m³
        
        # Pressure in Pascals
        pressure_pa = map_kpa * 1000.0
        
        # Temperature in Kelvin (use ambient temp as approximation)
        temp_k = (self.ambient_temp_f - 32) * 5/9 + KELVIN_OFFSET
        
        # Air mass (kg)
        air_mass_kg = (pressure_pa * displacement_m3) / (R_SPECIFIC_AIR * temp_k)
        
        # Convert to milligrams
        air_mass_mg = air_mass_kg * 1_000_000
        
        return air_mass_mg
    
    def calculate_required_fuel_mg(
        self, 
        rpm: float, 
        map_kpa: float, 
        target_afr: float | None = None
    ) -> float:
        """
        Calculate required fuel mass for target AFR.
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
            target_afr: Target AFR (if None, looks up from table)
        
        Returns:
            Required fuel mass in milligrams
        """
        # Get air mass
        air_mass_mg = self.calculate_air_mass_mg(rpm, map_kpa)
        
        # Get target AFR
        if target_afr is None:
            target_afr = self.lookup_target_afr(rpm, map_kpa)
        
        # Calculate fuel: AFR = air / fuel, so fuel = air / AFR
        fuel_mass_mg = air_mass_mg / target_afr
        
        return fuel_mass_mg
    
    def calculate_delivered_fuel_mg(
        self,
        rpm: float,
        map_kpa: float,
        cylinder: Literal['front', 'rear']
    ) -> float:
        """
        Calculate actual fuel delivered by ECU based on VE table.
        
        This is what the ECU THINKS is correct based on its VE table.
        If the VE table is wrong, the fuel delivery will be wrong!
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
            cylinder: Which cylinder ('front' or 'rear')
        
        Returns:
            Delivered fuel mass in milligrams
        """
        # Lookup VE from ECU's table
        ecu_ve = self.lookup_ve(rpm, map_kpa, cylinder)
        
        # Calculate base fuel requirement (for VE = 1.0)
        base_fuel_mg = self.calculate_required_fuel_mg(rpm, map_kpa)
        
        # Apply VE correction
        # Higher VE = more air in cylinder = need more fuel
        delivered_fuel_mg = base_fuel_mg * ecu_ve
        
        return delivered_fuel_mg
    
    def calculate_resulting_afr(
        self,
        rpm: float,
        map_kpa: float,
        actual_ve: float,
        cylinder: Literal['front', 'rear']
    ) -> float:
        """
        Calculate the AFR that results from ECU fueling vs actual VE.
        
        This is THE KEY FUNCTION for tuning simulation!
        
        When ECU's VE table doesn't match actual VE:
        - ECU VE < Actual VE → Lean (not enough fuel for actual air)
        - ECU VE > Actual VE → Rich (too much fuel for actual air)
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
            actual_ve: Actual volumetric efficiency from physics (0.0-1.5)
            cylinder: Which cylinder ('front' or 'rear')
        
        Returns:
            Resulting AFR that would be measured by wideband O2 sensor
        
        Example:
            >>> ecu = VirtualECU(...)
            >>> # ECU thinks VE = 0.85, but actual VE = 0.95
            >>> ecu.ve_table_front[rpm_idx, map_idx] = 0.85
            >>> afr = ecu.calculate_resulting_afr(3000, 80, actual_ve=0.95, 'front')
            >>> # Result: AFR will be LEAN (more air than fuel)
        """
        # What the ECU thinks VE is (from its table)
        ecu_ve = self.lookup_ve(rpm, map_kpa, cylinder)
        
        # Calculate VE error ratio
        ve_error_ratio = actual_ve / ecu_ve
        
        # Get target AFR from table
        target_afr = self.lookup_target_afr(rpm, map_kpa)
        
        # Calculate resulting AFR
        # If actual VE > ECU VE: More air than expected → Lean → Higher AFR
        # If actual VE < ECU VE: Less air than expected → Rich → Lower AFR
        resulting_afr = target_afr * ve_error_ratio
        
        # Clamp to physically reasonable range
        resulting_afr = np.clip(resulting_afr, 8.0, 20.0)
        
        return resulting_afr
    
    def get_ve_error_pct(
        self,
        rpm: float,
        map_kpa: float,
        actual_ve: float,
        cylinder: Literal['front', 'rear']
    ) -> float:
        """
        Calculate VE error percentage (for diagnostics).
        
        Args:
            rpm: Engine speed (RPM)
            map_kpa: Manifold absolute pressure (kPa)
            actual_ve: Actual volumetric efficiency from physics
            cylinder: Which cylinder ('front' or 'rear')
        
        Returns:
            VE error as percentage (positive = ECU underestimates VE)
        """
        ecu_ve = self.lookup_ve(rpm, map_kpa, cylinder)
        error_pct = ((actual_ve - ecu_ve) / ecu_ve) * 100.0
        return error_pct


def create_baseline_ve_table(
    rpm_bins: list[int] | None = None,
    map_bins: list[int] | None = None,
    peak_ve: float = 0.85,
    peak_rpm: int = 4000,
) -> np.ndarray:
    """
    Create a baseline VE table with realistic shape.
    
    VE follows a Gaussian-like distribution:
    - Peak VE at torque peak RPM
    - Lower VE at low RPM (poor scavenging)
    - Lower VE at high RPM (flow restrictions)
    - VE increases with MAP (better cylinder filling)
    
    Args:
        rpm_bins: RPM axis (default: standard DynoAI bins)
        map_bins: MAP axis in kPa (default: standard DynoAI bins)
        peak_ve: Peak VE value at optimal RPM/MAP
        peak_rpm: RPM where VE peaks
    
    Returns:
        VE table as numpy array (RPM x MAP)
    """
    if rpm_bins is None:
        rpm_bins = DEFAULT_RPM_BINS.copy()
    if map_bins is None:
        map_bins = DEFAULT_MAP_BINS.copy()
    
    ve_table = np.zeros((len(rpm_bins), len(map_bins)))
    
    for i, rpm in enumerate(rpm_bins):
        # Gaussian-like VE curve vs RPM
        rpm_factor = np.exp(-0.5 * ((rpm / peak_rpm - 1.0) / 0.4) ** 2)
        
        for j, map_kpa in enumerate(map_bins):
            # VE increases with MAP (more boost/less restriction)
            # At low MAP (vacuum), VE is reduced
            map_factor = 0.7 + 0.3 * (map_kpa / 100.0)
            
            ve_table[i, j] = peak_ve * rpm_factor * map_factor
    
    # Clamp to reasonable range
    ve_table = np.clip(ve_table, 0.4, 1.2)
    
    return ve_table


def create_afr_target_table(
    rpm_bins: list[int] | None = None,
    map_bins: list[int] | None = None,
    cruise_afr: float = 14.0,
    wot_afr: float = 12.5,
) -> np.ndarray:
    """
    Create an AFR target table with load-based targets.
    
    AFR strategy:
    - Light load (low MAP): Leaner for economy (13.5-14.0)
    - Medium load: Slightly rich (13.0-13.5)
    - High load (WOT): Rich for power and cooling (12.5-13.0)
    
    Args:
        rpm_bins: RPM axis (default: standard DynoAI bins)
        map_bins: MAP axis in kPa (default: standard DynoAI bins)
        cruise_afr: Target AFR at cruise/light load
        wot_afr: Target AFR at WOT/high load
    
    Returns:
        AFR target table as numpy array (RPM x MAP)
    """
    if rpm_bins is None:
        rpm_bins = DEFAULT_RPM_BINS.copy()
    if map_bins is None:
        map_bins = DEFAULT_MAP_BINS.copy()
    
    afr_table = np.zeros((len(rpm_bins), len(map_bins)))
    
    for i, rpm in enumerate(rpm_bins):
        for j, map_kpa in enumerate(map_bins):
            # Linear interpolation from cruise to WOT based on MAP
            # Low MAP (20 kPa) = cruise AFR
            # High MAP (100 kPa) = WOT AFR
            load_factor = (map_kpa - 20) / (100 - 20)
            load_factor = np.clip(load_factor, 0.0, 1.0)
            
            afr_table[i, j] = cruise_afr + (wot_afr - cruise_afr) * load_factor
    
    return afr_table


def create_intentionally_wrong_ve_table(
    baseline_table: np.ndarray,
    error_pct_mean: float = -10.0,
    error_pct_std: float = 5.0,
    seed: int | None = None,
) -> np.ndarray:
    """
    Create a VE table with intentional errors for testing tuning.
    
    This simulates a poorly tuned engine where the VE table doesn't
    match reality. Perfect for testing closed-loop tuning convergence!
    
    Args:
        baseline_table: Correct VE table
        error_pct_mean: Mean error percentage (negative = too lean)
        error_pct_std: Standard deviation of error
        seed: Random seed for reproducibility
    
    Returns:
        VE table with errors
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Generate random errors
    errors = np.random.normal(error_pct_mean, error_pct_std, baseline_table.shape)
    
    # Apply errors
    wrong_table = baseline_table * (1.0 + errors / 100.0)
    
    # Clamp to reasonable range
    wrong_table = np.clip(wrong_table, 0.3, 1.5)
    
    return wrong_table


def print_ecu_diagnostics(ecu: VirtualECU, rpm: float, map_kpa: float, actual_ve: float):
    """
    Print diagnostic information about ECU fueling at a specific point.
    
    Useful for debugging and understanding ECU behavior.
    """
    print(f"\n=== ECU Diagnostics at {rpm} RPM, {map_kpa} kPa ===")
    
    # Front cylinder
    ecu_ve_front = ecu.lookup_ve(rpm, map_kpa, 'front')
    target_afr = ecu.lookup_target_afr(rpm, map_kpa)
    air_mass = ecu.calculate_air_mass_mg(rpm, map_kpa)
    fuel_delivered = ecu.calculate_delivered_fuel_mg(rpm, map_kpa, 'front')
    resulting_afr = ecu.calculate_resulting_afr(rpm, map_kpa, actual_ve, 'front')
    ve_error = ecu.get_ve_error_pct(rpm, map_kpa, actual_ve, 'front')
    
    print(f"  Target AFR:        {target_afr:.2f}")
    print(f"  ECU VE (table):    {ecu_ve_front:.3f}")
    print(f"  Actual VE (phys):  {actual_ve:.3f}")
    print(f"  VE Error:          {ve_error:+.1f}%")
    print(f"  Air mass:          {air_mass:.1f} mg")
    print(f"  Fuel delivered:    {fuel_delivered:.1f} mg")
    print(f"  Resulting AFR:     {resulting_afr:.2f}")
    print(f"  AFR Error:         {resulting_afr - target_afr:+.2f}")

