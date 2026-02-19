"""
Temperature-dependent thermodynamics from NASA polynomials.

Coefficients are compatible with combustion_toolbox (databases/thermo_NASA.inp).
Used for expansion efficiency and gamma(T) in Engine Analyzer predictions.

Reference: Combustion Toolbox (Cuadra et al.), thermo_NASA.inp;
  cp/R = sum(a_i * T^e_i) with exponents e = [-2, -1, 0, 1, 2, 3, 4].
"""

from __future__ import annotations

import math
from typing import Literal

# Universal gas constant J/(mol·K)
R_MOL = 8.314462618

# NASA 7-coefficient polynomial (cp/R) per temperature range.
# Format: (T_low, T_high, (a1..a7)); cp/R = a1*T^-2 + a2*T^-1 + a3 + a4*T + a5*T^2 + a6*T^3 + a7*T^4
# Source: combustion_toolbox-master/databases/thermo_NASA.inp (same species/coefficients)
_NASA_COEFFS: dict[str, list[tuple[float, float, tuple[float, ...]]]] = {
    "N2": [
        (200.0, 1000.0, (2.210371497e04, -3.818461820e02, 6.082738360e00, -8.530914410e-03, 1.384646189e-05, -9.625793620e-09, 2.519705809e-12)),
        (1000.0, 6000.0, (5.877124060e05, -2.239249073e03, 6.066949220e00, -6.139685500e-04, 1.491806679e-07, -1.923105485e-11, 1.061954386e-15)),
        (6000.0, 20000.0, (8.310139160e08, -6.420733540e05, 2.020264635e02, -3.065092046e-02, 2.486903333e-06, -9.705954110e-11, 1.437538881e-15)),
    ],
    "O2": [
        (200.0, 1000.0, (-3.425563420e04, 4.847000970e02, 1.119010961e00, 4.293889240e-03, -6.836300520e-07, -2.023372700e-09, 1.039040018e-12)),
        (1000.0, 6000.0, (-1.037939022e06, 2.344830282e03, 1.819732036e00, 1.267847582e-03, -2.188067988e-07, 2.053719572e-11, -8.193467050e-16)),
        (6000.0, 20000.0, (4.975294300e08, -2.866106874e05, 6.690352250e01, -6.169959020e-03, 3.016396027e-07, -7.421416600e-12, 7.278175770e-17)),
    ],
    "CO2": [
        (200.0, 1000.0, (4.943650540e04, -6.264116010e02, 5.301725240e00, 2.503813816e-03, -2.127308728e-07, -7.689988780e-10, 2.849677801e-13)),
        (1000.0, 6000.0, (1.176962419e05, -1.788791477e03, 8.291523190e00, -9.223156780e-05, 4.863676880e-09, -1.891053312e-12, 6.330036590e-16)),
        (6000.0, 20000.0, (-1.544423287e09, 1.016847056e06, -2.561405230e02, 3.369401080e-02, -2.181184337e-06, 6.991420840e-11, -8.842351500e-16)),
    ],
    "H2O": [
        (200.0, 1000.0, (-3.947960830e04, 5.755731020e02, 9.317826530e-01, 7.222712860e-03, -7.342557370e-06, 4.955043490e-09, -1.336933246e-12)),
        (1000.0, 6000.0, (1.034972096e06, -2.412698562e03, 4.646110780e00, 2.291998307e-03, -6.836830480e-07, 9.426468930e-11, -4.822380530e-15)),
        (6000.0, 20000.0, (-2.040922112e07, -1.072691716e03, 1.131977392e01, -7.364445000e-04, 5.416450200e-08, -1.900872342e-12, 2.604761558e-17)),
    ],
}

# Mole fractions: air (N2, O2); burned stoichiometric gasoline ~ (N2, CO2, H2O)
AIR_MOLE_FRACTIONS: dict[str, float] = {"N2": 0.79, "O2": 0.21}
BURNED_MOLE_FRACTIONS: dict[str, float] = {"N2": 0.72, "CO2": 0.12, "H2O": 0.16}


def _cp_R_species(T: float, species: str) -> float:
    """cp/R (dimensionless) for a single species at T [K]."""
    if T <= 0:
        return 0.0
    ranges = _NASA_COEFFS.get(species)
    if not ranges:
        return 0.0
    for T_lo, T_hi, coeffs in ranges:
        if T_lo <= T < T_hi:
            a1, a2, a3, a4, a5, a6, a7 = coeffs
            # cp/R = a1*T^-2 + a2*T^-1 + a3 + a4*T + a5*T^2 + a6*T^3 + a7*T^4
            inv_T = 1.0 / T
            inv_T2 = inv_T * inv_T
            return a1 * inv_T2 + a2 * inv_T + a3 + a4 * T + a5 * (T * T) + a6 * (T * T * T) + a7 * (T * T * T * T)
    # Clamp to first or last range
    T_lo, T_hi, coeffs = ranges[0][0], ranges[-1][1], ranges[0][2] if T < ranges[0][1] else ranges[-1][2]
    T_clamp = max(T_lo, min(T_hi, T))
    return _cp_R_species(T_clamp, species)


def cp_mole_species(T: float, species: str) -> float:
    """Molar cp [J/(mol·K)] for species at T [K]."""
    return R_MOL * _cp_R_species(T, species)


def gamma_species(T: float, species: str) -> float:
    """Adiabatic index gamma = cp/cv for species at T [K]."""
    cp_R = _cp_R_species(T, species)
    if cp_R <= 1.0:
        return 1.4
    return cp_R / (cp_R - 1.0)


def _cp_R_mix(T: float, mole_fractions: dict[str, float]) -> float:
    """cp/R for mixture (mole-fraction weighted)."""
    return sum(mole_fractions[s] * _cp_R_species(T, s) for s in mole_fractions if s in _NASA_COEFFS)


def gamma_air(T: float) -> float:
    """Adiabatic index for air (0.79 N2, 0.21 O2) at T [K]. From combustion_toolbox thermo_NASA.inp."""
    cp_R = _cp_R_mix(T, AIR_MOLE_FRACTIONS)
    if cp_R <= 1.0:
        return 1.4
    return cp_R / (cp_R - 1.0)


def gamma_burned(T: float) -> float:
    """Adiabatic index for typical burned gas (N2, CO2, H2O) at T [K]. From combustion_toolbox thermo_NASA.inp."""
    cp_R = _cp_R_mix(T, BURNED_MOLE_FRACTIONS)
    if cp_R <= 1.0:
        return 1.3
    return cp_R / (cp_R - 1.0)


def expansion_efficiency_otto(gamma: float, compression_ratio: float) -> float:
    """Ideal Otto cycle expansion efficiency: 1 - 1/CR^(gamma-1)."""
    if compression_ratio <= 1.0 or gamma <= 1.0:
        return 0.0
    return 1.0 - 1.0 / (compression_ratio ** (gamma - 1.0))


def estimated_peak_cylinder_T_K(
    T_inlet_K: float = 300.0,
    compression_ratio: float = 10.0,
    mix: Literal["air", "burned"] = "burned",
) -> float:
    """Rough peak cylinder temperature [K] from inlet T and CR (isentropic compression then combustion)."""
    if compression_ratio <= 1.0:
        return T_inlet_K
    gamma_comp = gamma_air(T_inlet_K)
    # T2/T1 = CR^(gamma-1) for compression; then rough 2x for combustion
    T_after_comp = T_inlet_K * (compression_ratio ** (gamma_comp - 1.0))
    gamma_exp = gamma_burned(T_after_comp * 2.0) if mix == "burned" else gamma_air(T_after_comp)
    # Very rough: peak T ~ T_comp * (1 + Q/(cv*T)) ~ 2–2.5 * T_comp for stoichiometric
    return min(3500.0, T_after_comp * 2.2)
