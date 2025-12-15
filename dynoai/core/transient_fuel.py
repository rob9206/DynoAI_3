"""
Transient Fuel Compensation Analysis Module

This module analyzes transient engine conditions (acceleration/deceleration) and
calculates fuel compensation needed for wall-wetting effects and manifold dynamics.

Author: DynoAI_3
Date: 2025-12-15
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from scipy import signal
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

# Import environmental corrections
from dynoai.core.environmental import (
    EnvironmentalCorrector,
    EnvironmentalConditions,
    EnvironmentalCorrectionResult,
)


@dataclass
class TransientEvent:
    """Represents a single transient event (acceleration or deceleration)."""
    
    start_time: float
    end_time: float
    event_type: str  # 'accel' or 'decel'
    severity: str  # 'mild', 'moderate', 'aggressive'
    peak_map_rate: float  # kPa/sec
    peak_tps_rate: float  # %/sec
    avg_rpm: float
    afr_error_avg: float  # Average AFR error during event
    afr_error_peak: float  # Peak AFR error during event
    avg_iat_c: float = 25.0  # Average IAT during event in Celsius
    iat_category: str = 'warm'  # 'cold', 'cool', 'warm', 'hot'


@dataclass
class TauWallWettingParams:
    """
    Wall wetting model parameters based on the X-Tau model.
    
    The X-Tau model describes fuel transport dynamics in port injection:
    - X (chi): Fraction of injected fuel that wets the intake port wall (0-1)
    - Tau: Time constant for fuel evaporation from the wall (seconds)
    
    During acceleration (increasing fuel demand):
        m_fuel_injected = m_fuel_desired + X * tau * d(m_fuel_desired)/dt
        
    The extra fuel compensates for:
    1. Immediate wall wetting loss (X fraction sticks to wall)
    2. Evaporation delay (tau time constant)
    
    Typical values:
    - Cold engine: X=0.4, tau=3.0s
    - Warm engine: X=0.2, tau=1.0s
    - Hot engine: X=0.1, tau=0.5s
    """
    x_fraction: float  # Fraction of fuel that wets the wall (0-1)
    tau_seconds: float  # Time constant for evaporation (s)
    rpm_range: str  # RPM range this applies to
    temperature_condition: str  # 'cold', 'warm', 'hot'


@dataclass
class TransientFuelResult:
    """Results from transient fuel compensation analysis."""
    
    # Wall wetting factors by RPM range
    wall_wetting_factor: Dict[str, float] = field(default_factory=dict)
    
    # Tau-based wall wetting parameters (physics model)
    tau_wall_wetting_params: List[TauWallWettingParams] = field(default_factory=list)
    
    # Enrichment tables
    map_rate_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    tps_rate_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    transient_3d_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    decel_fuel_cut_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    # Analysis results
    afr_error_during_transients: List[Tuple[float, float]] = field(default_factory=list)
    detected_events: List[TransientEvent] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Plots
    plots: Dict[str, plt.Figure] = field(default_factory=dict)


class TransientFuelAnalyzer:
    """
    Analyzer for transient fuel compensation.
    
    This class provides methods to analyze dyno data for transient conditions
    and generate fuel compensation tables for Power Vision tuning.
    
    Args:
        target_afr: Target air-fuel ratio (default: 13.0)
        map_rate_threshold: MAP rate threshold for transient detection (kPa/sec, default: 50.0)
        tps_rate_threshold: TPS rate threshold for transient detection (%/sec, default: 20.0)
        afr_tolerance: AFR tolerance for error calculation (default: 0.5)
        sample_rate_hz: Expected sample rate of input data (default: 50.0 Hz)
        compensation_factor: Aggressiveness of fuel compensation recommendations (default: 0.65)
            - 0.25: Very conservative (similar to legacy behavior, ~2% per 1.0 AFR)
            - 0.50: Conservative (good for first-time tuning, ~4% per 1.0 AFR)
            - 0.65: Optimal (balanced accuracy vs safety, ~5% per 1.0 AFR) [DEFAULT]
            - 0.80: Aggressive (for experienced tuners, ~6% per 1.0 AFR)
            - 1.00: Full stoichiometric (theoretical maximum, ~7.7% per 1.0 AFR)
        iat_reference_c: Reference IAT for calibration in Celsius (default: 25.0°C)
            This is the baseline temperature where no IAT correction is applied.
            Typically set to dyno room temperature or ECU calibration temperature.
        iat_density_coeff: IAT density correction coefficient (default: 0.0035)
            Air density changes ~0.35% per °C. This affects required fuel mass.
            Higher values = more aggressive temperature compensation.
        iat_wall_wetting_coeff: IAT wall wetting coefficient (default: 0.025)
            Wall wetting increases ~2.5% per °C below reference (cold = more wetting).
            This affects X (wall wetting fraction) and tau (evaporation time).
        environmental_conditions: Optional atmospheric conditions for correction
            If provided, all enrichment calculations will be adjusted for:
            - Barometric pressure / altitude
            - Ambient temperature
            - Humidity
            - Engine coolant temperature (ECT)
        
    Example:
        >>> df = pd.read_csv('dyno_run_with_accel.csv')
        >>> analyzer = TransientFuelAnalyzer(target_afr=13.0)
        >>> result = analyzer.analyze_transients(df)
        >>> for rec in result.recommendations:
        ...     print(rec)
        
        # For more aggressive tuning:
        >>> analyzer = TransientFuelAnalyzer(target_afr=13.0, compensation_factor=0.80)
        
        # For cold weather tuning (reference temp 10°C):
        >>> analyzer = TransientFuelAnalyzer(target_afr=13.0, iat_reference_c=10.0)
        
        # For high altitude tuning (Denver, ~5000 ft):
        >>> from dynoai.core.environmental import EnvironmentalConditions
        >>> conditions = EnvironmentalConditions(barometric_pressure_inhg=24.89)
        >>> analyzer = TransientFuelAnalyzer(
        ...     target_afr=13.0,
        ...     environmental_conditions=conditions,
        ... )
    """
    
    def __init__(
        self,
        target_afr: float = 13.0,
        map_rate_threshold: float = 50.0,
        tps_rate_threshold: float = 20.0,
        afr_tolerance: float = 0.5,
        sample_rate_hz: float = 50.0,
        compensation_factor: float = 0.65,
        iat_reference_c: float = 25.0,
        iat_density_coeff: float = 0.0035,
        iat_wall_wetting_coeff: float = 0.025,
        environmental_conditions: Optional[EnvironmentalConditions] = None,
    ):
        self.target_afr = target_afr
        self.map_rate_threshold = map_rate_threshold
        self.tps_rate_threshold = tps_rate_threshold
        self.afr_tolerance = afr_tolerance
        self.sample_rate_hz = sample_rate_hz
        self.compensation_factor = max(0.1, min(compensation_factor, 1.0))  # Clamp 0.1-1.0
        
        # IAT compensation parameters
        self.iat_reference_c = iat_reference_c
        self.iat_density_coeff = iat_density_coeff
        self.iat_wall_wetting_coeff = iat_wall_wetting_coeff
        
        # Environmental conditions (for altitude, humidity, etc.)
        self.environmental_conditions = environmental_conditions
        self._env_corrector = EnvironmentalCorrector() if environmental_conditions else None
        self._env_correction: Optional[EnvironmentalCorrectionResult] = None
        
        # Calculate environmental correction if conditions provided
        if environmental_conditions:
            self._env_correction = self._env_corrector.calculate(environmental_conditions)
    
    def _calculate_iat_density_factor(self, iat_c: float) -> float:
        """
        Calculate air density correction factor based on IAT.
        
        Cold air is denser, requiring more fuel mass for the same AFR.
        Based on ideal gas law: density ∝ 1/T (in Kelvin)
        
        Simplified linear approximation:
        factor = 1 + (T_ref - T_actual) * density_coeff
        
        Args:
            iat_c: Intake air temperature in Celsius
            
        Returns:
            Density correction factor (>1 for cold, <1 for hot)
            
        Example:
            Reference 25°C, actual 0°C: factor = 1 + (25-0)*0.0035 = 1.0875 (+8.75%)
            Reference 25°C, actual 50°C: factor = 1 + (25-50)*0.0035 = 0.9125 (-8.75%)
        """
        delta_t = self.iat_reference_c - iat_c
        factor = 1.0 + (delta_t * self.iat_density_coeff)
        return max(0.85, min(factor, 1.20))  # Clamp to ±15-20%
    
    def _calculate_iat_wall_wetting_factor(self, iat_c: float) -> float:
        """
        Calculate wall wetting scaling factor based on IAT.
        
        Cold conditions increase wall wetting (fuel sticks to cold port walls)
        and slow evaporation (fuel takes longer to vaporize from cold surfaces).
        
        This factor scales X (wall wetting fraction) and tau (time constant).
        
        Args:
            iat_c: Intake air temperature in Celsius
            
        Returns:
            Wall wetting scaling factor (>1 for cold = more wetting, <1 for hot)
            
        Example:
            Reference 25°C, actual 0°C: factor = 1 + (25-0)*0.025 = 1.625 (+62.5% wall wetting)
            Reference 25°C, actual 50°C: factor = 1 + (25-50)*0.025 = 0.375 (-62.5% wall wetting)
        """
        delta_t = self.iat_reference_c - iat_c
        factor = 1.0 + (delta_t * self.iat_wall_wetting_coeff)
        return max(0.3, min(factor, 2.5))  # Clamp to reasonable range
    
    def _get_iat_category(self, iat_c: float) -> str:
        """
        Categorize IAT into cold/warm/hot for reporting.
        
        Args:
            iat_c: Intake air temperature in Celsius
            
        Returns:
            Category string: 'cold', 'cool', 'warm', 'hot'
        """
        if iat_c < 10:
            return 'cold'
        elif iat_c < 25:
            return 'cool'
        elif iat_c < 45:
            return 'warm'
        else:
            return 'hot'
        
    def analyze_transients(self, df: pd.DataFrame) -> TransientFuelResult:
        """
        Analyze transient events in dyno data.
        
        Args:
            df: DataFrame with columns [time, rpm, map, tps, afr, iat, target_afr (optional)]
            
        Returns:
            TransientFuelResult with comprehensive analysis
            
        Raises:
            ValueError: If required columns are missing or data is invalid
        """
        # Validate input
        self._validate_input(df)
        
        # Use provided target_afr column if available, otherwise use instance default
        if 'target_afr' not in df.columns:
            df = df.copy()
            df['target_afr'] = self.target_afr
        
        # Calculate rates
        df = self._calculate_rates(df)
        
        # Detect transient events
        events = self.detect_transient_events(df)
        
        # Calculate enrichment tables
        map_rate_table = self.calculate_map_rate_enrichment(df, events)
        tps_rate_table = self.calculate_tps_rate_enrichment(df, events)
        transient_3d_table = self._calculate_3d_enrichment(df, events)
        decel_table = self._calculate_decel_fuel_cut(df, events)
        
        # Calculate wall wetting factors
        wall_wetting = self.calculate_wall_wetting_compensation(df, events)
        
        # Calculate tau-based wall wetting parameters (physics model)
        tau_params = self.calculate_tau_wall_wetting(df, events)
        
        # Extract AFR errors during transients
        afr_errors = self._extract_afr_errors(df, events)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(df, events, afr_errors)
        
        # Create plots
        plots = self._create_plots(df, events, map_rate_table, tps_rate_table)
        
        return TransientFuelResult(
            wall_wetting_factor=wall_wetting,
            tau_wall_wetting_params=tau_params,
            map_rate_table=map_rate_table,
            tps_rate_table=tps_rate_table,
            transient_3d_table=transient_3d_table,
            decel_fuel_cut_table=decel_table,
            afr_error_during_transients=afr_errors,
            detected_events=events,
            recommendations=recommendations,
            plots=plots,
        )
    
    def _validate_input(self, df: pd.DataFrame) -> None:
        """Validate input DataFrame has required columns and valid data."""
        required_cols = ['time', 'rpm', 'map', 'tps', 'afr']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        if len(df) < 10:
            raise ValueError("Insufficient data points (need at least 10)")
        
        # Check for reasonable values
        if df['rpm'].max() > 20000 or df['rpm'].min() < 0:
            raise ValueError("RPM values out of reasonable range")
        
        if df['map'].max() > 500 or df['map'].min() < 0:
            raise ValueError("MAP values out of reasonable range (0-500 kPa)")
        
        if df['tps'].max() > 100 or df['tps'].min() < 0:
            raise ValueError("TPS values out of reasonable range (0-100%)")
    
    def _calculate_rates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate rate of change for MAP and TPS."""
        df = df.copy()
        
        # Calculate time delta
        dt = df['time'].diff().fillna(1.0 / self.sample_rate_hz)
        
        # Calculate rates (smooth with small window to reduce noise)
        window = 3  # 3-point moving average
        df['map_rate'] = df['map'].diff().fillna(0) / dt
        df['map_rate'] = df['map_rate'].rolling(window=window, center=True, min_periods=1).mean()
        
        df['tps_rate'] = df['tps'].diff().fillna(0) / dt
        df['tps_rate'] = df['tps_rate'].rolling(window=window, center=True, min_periods=1).mean()
        
        return df
    
    def detect_transient_events(self, df: pd.DataFrame) -> List[TransientEvent]:
        """
        Detect transient events (acceleration/deceleration) in the data.
        
        Args:
            df: DataFrame with calculated rates
            
        Returns:
            List of TransientEvent objects
        """
        events = []
        
        # Find periods where MAP or TPS rate exceeds thresholds
        accel_mask = (
            (df['map_rate'].abs() > self.map_rate_threshold) |
            (df['tps_rate'].abs() > self.tps_rate_threshold)
        )
        
        # Find continuous regions
        event_regions = self._find_continuous_regions(accel_mask)
        
        for start_idx, end_idx in event_regions:
            if end_idx - start_idx < 3:  # Skip very short events
                continue
            
            event_data = df.iloc[start_idx:end_idx]
            
            # Determine event type
            avg_map_rate = event_data['map_rate'].mean()
            avg_tps_rate = event_data['tps_rate'].mean()
            
            if avg_map_rate > 0 or avg_tps_rate > 0:
                event_type = 'accel'
            else:
                event_type = 'decel'
            
            # Determine severity
            peak_map_rate = event_data['map_rate'].abs().max()
            peak_tps_rate = event_data['tps_rate'].abs().max()
            
            if peak_map_rate > 150 or peak_tps_rate > 60:
                severity = 'aggressive'
            elif peak_map_rate > 100 or peak_tps_rate > 40:
                severity = 'moderate'
            else:
                severity = 'mild'
            
            # Calculate AFR error
            afr_error = event_data['afr'] - event_data['target_afr']
            afr_error_avg = afr_error.mean()
            afr_error_peak = afr_error.abs().max()
            
            # Calculate average IAT during event
            if 'iat' in event_data.columns:
                avg_iat = event_data['iat'].mean()
                iat_category = self._get_iat_category(avg_iat)
            else:
                avg_iat = self.iat_reference_c  # Default to reference if no IAT data
                iat_category = 'warm'
            
            event = TransientEvent(
                start_time=event_data['time'].iloc[0],
                end_time=event_data['time'].iloc[-1],
                event_type=event_type,
                severity=severity,
                peak_map_rate=peak_map_rate,
                peak_tps_rate=peak_tps_rate,
                avg_rpm=event_data['rpm'].mean(),
                afr_error_avg=afr_error_avg,
                afr_error_peak=afr_error_peak,
                avg_iat_c=avg_iat,
                iat_category=iat_category,
            )
            events.append(event)
        
        return events
    
    def _find_continuous_regions(self, mask: pd.Series) -> List[Tuple[int, int]]:
        """Find continuous True regions in a boolean mask."""
        regions = []
        in_region = False
        start_idx = 0
        
        for idx, val in enumerate(mask):
            if val and not in_region:
                start_idx = idx
                in_region = True
            elif not val and in_region:
                regions.append((start_idx, idx))
                in_region = False
        
        # Handle case where region extends to end
        if in_region:
            regions.append((start_idx, len(mask)))
        
        return regions
    
    def calculate_map_rate_enrichment(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> pd.DataFrame:
        """
        Calculate MAP rate-based enrichment table with IAT correction.
        
        The enrichment values are adjusted based on the IAT during each event:
        - Cold IAT: Higher enrichment (denser air, more wall wetting)
        - Hot IAT: Lower enrichment (less dense air, less wall wetting)
        
        Args:
            df: DataFrame with rates calculated
            events: List of detected transient events
            
        Returns:
            DataFrame with MAP rate bins, enrichment percentages, and avg IAT
        """
        # Define MAP rate bins (kPa/sec)
        map_rate_bins = np.array([
            -200, -150, -100, -50, -25, 0, 25, 50, 100, 150, 200, 300
        ])
        
        # Initialize enrichment values and IAT tracking
        enrichment = np.zeros(len(map_rate_bins) - 1)
        iat_sum = np.zeros(len(map_rate_bins) - 1)
        iat_count = np.zeros(len(map_rate_bins) - 1)
        
        # For each event, correlate MAP rate to AFR error with IAT correction
        for event in events:
            if event.event_type != 'accel':
                continue
            
            # Find the bin for this event's peak MAP rate
            bin_idx = np.digitize(event.peak_map_rate, map_rate_bins) - 1
            if 0 <= bin_idx < len(enrichment):
                # Calculate needed enrichment based on AFR error and IAT
                # Pass the event's IAT for temperature-corrected enrichment
                needed_enrichment = self._afr_error_to_enrichment(
                    event.afr_error_avg, 
                    iat_c=event.avg_iat_c
                )
                enrichment[bin_idx] = max(enrichment[bin_idx], needed_enrichment)
                
                # Track IAT for reporting
                iat_sum[bin_idx] += event.avg_iat_c
                iat_count[bin_idx] += 1
        
        # Calculate average IAT per bin (avoid division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            avg_iat = np.where(iat_count > 0, iat_sum / iat_count, self.iat_reference_c)
        
        # Create table
        bin_centers = (map_rate_bins[:-1] + map_rate_bins[1:]) / 2
        table = pd.DataFrame({
            'map_rate_kpa_per_sec': bin_centers,
            'enrichment_percent': enrichment,
            'avg_iat_c': avg_iat,
        })
        
        return table
    
    def calculate_tps_rate_enrichment(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> pd.DataFrame:
        """
        Calculate TPS rate-based enrichment table with IAT correction.
        
        The enrichment values are adjusted based on the IAT during each event:
        - Cold IAT: Higher enrichment (denser air, more wall wetting)
        - Hot IAT: Lower enrichment (less dense air, less wall wetting)
        
        Args:
            df: DataFrame with rates calculated
            events: List of detected transient events
            
        Returns:
            DataFrame with TPS rate bins, enrichment percentages, and avg IAT
        """
        # Define TPS rate bins (%/sec)
        tps_rate_bins = np.array([
            -100, -75, -50, -25, -10, 0, 10, 25, 50, 75, 100, 150
        ])
        
        # Initialize enrichment values and IAT tracking
        enrichment = np.zeros(len(tps_rate_bins) - 1)
        iat_sum = np.zeros(len(tps_rate_bins) - 1)
        iat_count = np.zeros(len(tps_rate_bins) - 1)
        
        # For each event, correlate TPS rate to AFR error with IAT correction
        for event in events:
            if event.event_type != 'accel':
                continue
            
            bin_idx = np.digitize(event.peak_tps_rate, tps_rate_bins) - 1
            if 0 <= bin_idx < len(enrichment):
                # Calculate needed enrichment based on AFR error and IAT
                needed_enrichment = self._afr_error_to_enrichment(
                    event.afr_error_avg,
                    iat_c=event.avg_iat_c
                )
                enrichment[bin_idx] = max(enrichment[bin_idx], needed_enrichment)
                
                # Track IAT for reporting
                iat_sum[bin_idx] += event.avg_iat_c
                iat_count[bin_idx] += 1
        
        # Calculate average IAT per bin (avoid division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            avg_iat = np.where(iat_count > 0, iat_sum / iat_count, self.iat_reference_c)
        
        # Create table
        bin_centers = (tps_rate_bins[:-1] + tps_rate_bins[1:]) / 2
        table = pd.DataFrame({
            'tps_rate_percent_per_sec': bin_centers,
            'enrichment_percent': enrichment,
            'avg_iat_c': avg_iat,
        })
        
        return table
    
    def calculate_wall_wetting_compensation(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> Dict[str, float]:
        """
        Calculate wall wetting compensation factors by RPM range.
        
        Includes IAT-based correction: cold conditions increase wall wetting
        and slow evaporation, requiring more fuel compensation.
        
        Args:
            df: DataFrame with engine data
            events: List of transient events
            
        Returns:
            Dictionary mapping RPM ranges to compensation factors
        """
        # Define RPM ranges
        rpm_ranges = [
            ('idle', 0, 1500),
            ('low', 1500, 3000),
            ('mid', 3000, 5000),
            ('high', 5000, 8000),
            ('redline', 8000, 20000),
        ]
        
        factors = {}
        
        for range_name, rpm_min, rpm_max in rpm_ranges:
            # Find events in this RPM range
            range_events = [
                e for e in events
                if rpm_min <= e.avg_rpm < rpm_max and e.event_type == 'accel'
            ]
            
            if not range_events:
                factors[range_name] = 1.0  # No compensation needed
                continue
            
            # Average AFR error and IAT in this range
            avg_error = np.mean([e.afr_error_avg for e in range_events])
            avg_iat = np.mean([e.avg_iat_c for e in range_events])
            
            # Calculate IAT-based density and wall wetting factors
            iat_density_factor = self._calculate_iat_density_factor(avg_iat)
            iat_ww_factor = self._calculate_iat_wall_wetting_factor(avg_iat)
            
            # Convert to compensation factor using stoichiometric relationship
            # Positive error = lean = need more fuel = factor > 1.0
            #
            # Wall wetting during transients requires compensation for fuel film
            # dynamics that cause transport delays. The compensation_factor scales
            # the theoretical correction for safety.
            #
            # IAT corrections:
            # - iat_density_factor: adjusts for air density (cold air = more fuel needed)
            # - iat_ww_factor: adjusts for wall wetting (cold = more wetting, more fuel needed)
            #
            # Combined factor = 1.0 + (AFR_error / target_AFR) * comp_factor * iat_density * iat_ww
            base_correction = (avg_error / self.target_afr) * self.compensation_factor
            iat_adjusted_correction = base_correction * iat_density_factor * iat_ww_factor
            
            factor = 1.0 + iat_adjusted_correction
            factor = np.clip(factor, 0.85, 1.25)  # Wider range for IAT extremes
            
            factors[range_name] = round(factor, 3)
        
        return factors
    
    def calculate_tau_wall_wetting(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> List[TauWallWettingParams]:
        """
        Calculate X-Tau wall wetting model parameters from transient data.
        
        The X-Tau model is a physics-based approach to transient fuel compensation:
        
        m_inj = m_desired * (1 + X * tau * d(ln(m_desired))/dt)
        
        Where:
        - m_inj: Actual fuel mass to inject
        - m_desired: Desired fuel mass for target AFR
        - X: Wall wetting fraction (fuel that sticks to port walls)
        - tau: Time constant for fuel evaporation from walls
        
        Both X and tau are strongly affected by temperature:
        - Cold conditions: Higher X (more fuel sticks), higher tau (slower evap)
        - Hot conditions: Lower X (less sticking), lower tau (faster evap)
        
        This method estimates X and tau by analyzing the relationship between
        fuel demand rate-of-change, observed AFR error, and IAT.
        
        Args:
            df: DataFrame with calculated rates
            events: List of detected transient events
            
        Returns:
            List of TauWallWettingParams for different RPM ranges
        """
        params_list = []
        
        # Define RPM ranges
        rpm_ranges = [
            ('idle', 0, 1500),
            ('low', 1500, 3000),
            ('mid', 3000, 5000),
            ('high', 5000, 8000),
            ('redline', 8000, 20000),
        ]
        
        for range_name, rpm_min, rpm_max in rpm_ranges:
            # Find acceleration events in this RPM range
            range_events = [
                e for e in events
                if rpm_min <= e.avg_rpm < rpm_max and e.event_type == 'accel'
            ]
            
            if not range_events:
                # Default conservative parameters when no data
                params = TauWallWettingParams(
                    x_fraction=0.15,  # 15% wall wetting
                    tau_seconds=1.0,  # 1 second time constant
                    rpm_range=range_name,
                    temperature_condition='warm',
                )
                params_list.append(params)
                continue
            
            # Get average values from events
            avg_error = np.mean([e.afr_error_avg for e in range_events])
            avg_duration = np.mean([e.end_time - e.start_time for e in range_events])
            avg_map_rate = np.mean([e.peak_map_rate for e in range_events])
            avg_iat = np.mean([e.avg_iat_c for e in range_events])
            
            # Calculate IAT-based wall wetting scaling
            # Cold conditions increase X and tau significantly
            iat_ww_factor = self._calculate_iat_wall_wetting_factor(avg_iat)
            
            # Estimate X: positive AFR error means lean, fuel went to wall
            # X = (AFR_error / target_AFR) * compensation_factor * iat_ww_factor
            # IAT factor increases X in cold conditions (more wall wetting)
            base_x = (avg_error / self.target_afr) * self.compensation_factor
            x_estimate = base_x * iat_ww_factor
            x_estimate = max(0.05, min(x_estimate, 0.50))  # Wider range for cold conditions
            
            # Estimate tau: faster transients need shorter time constants
            # Higher MAP rates = faster transient = shorter tau
            # Cold conditions = longer tau (slower evaporation)
            base_tau = avg_duration / 3.0
            rate_factor = max(0.5, min(2.0, 100.0 / max(avg_map_rate, 50.0)))
            tau_estimate = base_tau * rate_factor * iat_ww_factor  # IAT increases tau when cold
            tau_estimate = max(0.2, min(tau_estimate, 8.0))  # Wider range for cold conditions
            
            # Temperature condition from actual IAT, not inferred from tau
            temp_condition = self._get_iat_category(avg_iat)
            
            params = TauWallWettingParams(
                x_fraction=round(x_estimate, 3),
                tau_seconds=round(tau_estimate, 2),
                rpm_range=range_name,
                temperature_condition=temp_condition,
            )
            params_list.append(params)
        
        return params_list
    
    def calculate_tau_enrichment(
        self, map_rate: float, tau_params: TauWallWettingParams
    ) -> float:
        """
        Calculate instantaneous enrichment using X-Tau model.
        
        The X-Tau enrichment formula for tip-in:
        Enrichment % = X * tau * (d(MAP)/dt / MAP) * 100
        
        This represents the extra fuel needed to compensate for wall wetting
        during transient conditions. Note that X already incorporates the
        compensation_factor from when tau_params were calculated.
        
        Args:
            map_rate: Current MAP rate of change (kPa/sec)
            tau_params: Wall wetting parameters for current RPM range
            
        Returns:
            Enrichment percentage (0-25% capped)
        """
        if map_rate <= 0:
            return 0.0  # Only enrich on acceleration
        
        # Simplified enrichment calculation
        # Full model: enrichment = X * tau * d(ln(m_fuel))/dt
        # Approximation: enrichment ≈ X * tau * (MAP_rate / MAP_avg) * scale
        #
        # Using average MAP of 100 kPa as reference:
        # enrichment % = X * tau * (MAP_rate / 100) * 100
        # Note: X already has compensation_factor baked in from calculate_tau_wall_wetting
        
        enrichment = tau_params.x_fraction * tau_params.tau_seconds * (map_rate / 100.0) * 100.0
        return max(0, min(enrichment, 25))  # Cap at 25%

    def _calculate_3d_enrichment(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> pd.DataFrame:
        """
        Calculate 3D enrichment table (RPM x MAP Rate x Enrichment) with IAT.
        
        This creates a comprehensive table that accounts for:
        - RPM range (affects airflow dynamics)
        - MAP rate (transient severity)
        - IAT (air density and wall wetting effects)
        """
        # Define bins
        rpm_bins = np.array([0, 2000, 3000, 4000, 5000, 6000, 7000, 8000])
        map_rate_bins = np.array([0, 50, 100, 150, 200, 300])
        
        # Create grid
        rows = []
        for rpm_idx in range(len(rpm_bins) - 1):
            for map_idx in range(len(map_rate_bins) - 1):
                rpm_center = (rpm_bins[rpm_idx] + rpm_bins[rpm_idx + 1]) / 2
                map_rate_center = (map_rate_bins[map_idx] + map_rate_bins[map_idx + 1]) / 2
                
                # Find events in this cell
                cell_events = [
                    e for e in events
                    if (rpm_bins[rpm_idx] <= e.avg_rpm < rpm_bins[rpm_idx + 1] and
                        map_rate_bins[map_idx] <= e.peak_map_rate < map_rate_bins[map_idx + 1] and
                        e.event_type == 'accel')
                ]
                
                if cell_events:
                    avg_error = np.mean([e.afr_error_avg for e in cell_events])
                    avg_iat = np.mean([e.avg_iat_c for e in cell_events])
                    # Pass IAT for temperature-corrected enrichment
                    enrichment = self._afr_error_to_enrichment(avg_error, iat_c=avg_iat)
                    iat_category = self._get_iat_category(avg_iat)
                else:
                    enrichment = 0.0
                    avg_iat = self.iat_reference_c
                    iat_category = 'warm'
                
                rows.append({
                    'rpm': rpm_center,
                    'map_rate_kpa_per_sec': map_rate_center,
                    'enrichment_percent': enrichment,
                    'avg_iat_c': avg_iat,
                    'iat_category': iat_category,
                })
        
        return pd.DataFrame(rows)
    
    def _calculate_decel_fuel_cut(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> pd.DataFrame:
        """Calculate deceleration fuel cut table."""
        # Define RPM bins
        rpm_bins = np.array([0, 2000, 3000, 4000, 5000, 6000, 7000, 8000])
        
        rows = []
        for rpm_idx in range(len(rpm_bins) - 1):
            rpm_center = (rpm_bins[rpm_idx] + rpm_bins[rpm_idx + 1]) / 2
            
            # Find decel events in this RPM range
            decel_events = [
                e for e in events
                if (rpm_bins[rpm_idx] <= e.avg_rpm < rpm_bins[rpm_idx + 1] and
                    e.event_type == 'decel')
            ]
            
            if decel_events:
                # Recommend fuel cut if AFR goes rich during decel
                avg_error = np.mean([e.afr_error_avg for e in decel_events])
                fuel_cut_percent = max(0, -avg_error * 5)  # 5% cut per 1.0 AFR rich
                fuel_cut_percent = min(fuel_cut_percent, 50)  # Max 50% cut
            else:
                fuel_cut_percent = 0.0
            
            rows.append({
                'rpm': rpm_center,
                'fuel_cut_percent': fuel_cut_percent,
            })
        
        return pd.DataFrame(rows)
    
    def _afr_error_to_enrichment(self, afr_error: float, iat_c: Optional[float] = None) -> float:
        """
        Convert AFR error to enrichment percentage using stoichiometric relationship.
        
        The fuel correction needed to achieve target AFR is derived from:
        AFR = (air mass) / (fuel mass)
        
        If actual AFR is higher than target (lean), we need more fuel:
        Fuel correction % = ((AFR_actual - AFR_target) / AFR_target) * 100
        
        For AFR error (actual - target):
        Enrichment % = (AFR_error / target_AFR) * 100 * compensation_factor * iat_density_factor
        
        The compensation_factor scales the theoretical value for safety:
        - 0.65 (default): ~5% per 1.0 AFR error - balanced accuracy vs safety
        - 1.00 (full): ~7.7% per 1.0 AFR error - theoretical maximum
        
        The iat_density_factor adjusts for air density changes with temperature:
        - Cold air (<25°C): denser, needs more fuel → factor > 1.0
        - Hot air (>25°C): less dense, needs less fuel → factor < 1.0
        
        Example with default factor (0.65) at 0°C IAT:
        Base enrichment = (1.0 / 13.0) * 100 * 0.65 = 5.0%
        IAT factor = 1.0875 (cold air is denser)
        Final enrichment = 5.0% * 1.0875 = 5.44%
        
        Args:
            afr_error: AFR actual - AFR target (positive = lean, negative = rich)
            iat_c: Intake air temperature in Celsius (optional, uses reference if None)
            
        Returns:
            Enrichment percentage (0-25%, capped for safety)
        """
        # Calculate IAT density correction
        if iat_c is not None:
            iat_factor = self._calculate_iat_density_factor(iat_c)
        else:
            iat_factor = 1.0
        
        # Calculate environmental correction (altitude, humidity, ECT, etc.)
        if self._env_correction is not None:
            env_factor = self._env_correction.total_correction
        else:
            env_factor = 1.0
        
        # Stoichiometric relationship scaled by compensation factor, IAT, and environment
        # env_factor < 1.0 at altitude means less fuel needed overall
        enrichment = (afr_error / self.target_afr) * 100 * self.compensation_factor * iat_factor * env_factor
        return max(0, min(enrichment, 25))  # Cap at 25% enrichment for safety
    
    def _extract_afr_errors(
        self, df: pd.DataFrame, events: List[TransientEvent]
    ) -> List[Tuple[float, float]]:
        """Extract AFR errors during transient events."""
        errors = []
        for event in events:
            mask = (df['time'] >= event.start_time) & (df['time'] <= event.end_time)
            event_data = df[mask]
            for _, row in event_data.iterrows():
                error_pct = ((row['afr'] - row['target_afr']) / row['target_afr']) * 100
                errors.append((row['time'], error_pct))
        return errors
    
    def _generate_recommendations(
        self, df: pd.DataFrame, events: List[TransientEvent], afr_errors: List[Tuple[float, float]]
    ) -> List[str]:
        """Generate tuning recommendations based on analysis."""
        recommendations = []
        
        if not events:
            recommendations.append("No significant transient events detected.")
            return recommendations
        
        # Count event types
        accel_events = [e for e in events if e.event_type == 'accel']
        decel_events = [e for e in events if e.event_type == 'decel']
        
        recommendations.append(
            f"Detected {len(accel_events)} acceleration events and "
            f"{len(decel_events)} deceleration events."
        )
        
        # Analyze acceleration events
        if accel_events:
            avg_accel_error = np.mean([e.afr_error_avg for e in accel_events])
            max_accel_error = max([e.afr_error_peak for e in accel_events])
            
            if avg_accel_error > self.afr_tolerance:
                recommendations.append(
                    f"Acceleration events show lean condition (avg error: {avg_accel_error:.2f} AFR). "
                    f"Increase transient enrichment by {self._afr_error_to_enrichment(avg_accel_error):.1f}%."
                )
            elif avg_accel_error < -self.afr_tolerance:
                recommendations.append(
                    f"Acceleration events show rich condition (avg error: {avg_accel_error:.2f} AFR). "
                    "Reduce transient enrichment."
                )
            else:
                recommendations.append("Acceleration fueling is within tolerance.")
        
        # Analyze deceleration events
        if decel_events:
            avg_decel_error = np.mean([e.afr_error_avg for e in decel_events])
            
            if avg_decel_error < -self.afr_tolerance:
                recommendations.append(
                    f"Deceleration events show rich condition (avg error: {avg_decel_error:.2f} AFR). "
                    "Enable or increase decel fuel cut."
                )
        
        # Severity-based recommendations
        aggressive_events = [e for e in events if e.severity == 'aggressive']
        if aggressive_events:
            recommendations.append(
                f"Detected {len(aggressive_events)} aggressive transient events. "
                "Consider adding MAP/TPS rate-based compensation tables."
            )
        
        # Calculate and add tau-based recommendations
        tau_params = self.calculate_tau_wall_wetting(df, events)
        if tau_params:
            high_x_params = [p for p in tau_params if p.x_fraction > 0.20]
            if high_x_params:
                ranges = ', '.join([p.rpm_range for p in high_x_params])
                avg_x = np.mean([p.x_fraction for p in high_x_params])
                recommendations.append(
                    f"X-Tau model shows high wall wetting (X={avg_x:.1%}) in {ranges} RPM ranges. "
                    f"This indicates significant fuel film buildup during tip-in."
                )
            
            long_tau_params = [p for p in tau_params if p.tau_seconds > 2.0]
            if long_tau_params:
                ranges = ', '.join([p.rpm_range for p in long_tau_params])
                recommendations.append(
                    f"Long time constants (tau > 2s) detected in {ranges} ranges. "
                    "This may indicate cold engine conditions or slow evaporation."
                )
        
        # Add IAT-based recommendations
        if events:
            avg_iat = np.mean([e.avg_iat_c for e in events])
            iat_category = self._get_iat_category(avg_iat)
            
            if iat_category == 'cold':
                iat_density = self._calculate_iat_density_factor(avg_iat)
                iat_ww = self._calculate_iat_wall_wetting_factor(avg_iat)
                recommendations.append(
                    f"Cold IAT detected (avg {avg_iat:.1f}°C). "
                    f"Air density factor: {iat_density:.3f}, wall wetting factor: {iat_ww:.2f}. "
                    f"Enrichment values are increased to compensate."
                )
            elif iat_category == 'hot':
                iat_density = self._calculate_iat_density_factor(avg_iat)
                recommendations.append(
                    f"Hot IAT detected (avg {avg_iat:.1f}°C). "
                    f"Air density factor: {iat_density:.3f}. "
                    f"Enrichment values are reduced accordingly."
                )
            
            # Check for IAT variation during run
            iat_std = np.std([e.avg_iat_c for e in events])
            if iat_std > 10:
                recommendations.append(
                    f"High IAT variation detected (σ={iat_std:.1f}°C). "
                    "Consider separate calibrations for cold-start and hot conditions."
                )
        
        # Add environmental correction recommendations
        if self._env_correction is not None:
            env = self._env_correction
            if not env.is_standard_day:
                env_pct = (env.total_correction - 1.0) * 100
                recommendations.append(
                    f"Environmental correction applied: {env_pct:+.1f}% "
                    f"(altitude: {env.pressure_correction:.3f}, "
                    f"temp: {env.temperature_correction:.3f}, "
                    f"humidity: {env.humidity_correction:.3f})"
                )
                
                if env.pressure_correction < 0.90:
                    altitude = self.environmental_conditions.altitude_ft or 0
                    recommendations.append(
                        f"High altitude detected (~{altitude:.0f} ft). "
                        f"Enrichment values reduced by {(1-env.pressure_correction)*100:.1f}% "
                        "to compensate for thinner air."
                    )
        
        return recommendations
    
    def _create_plots(
        self,
        df: pd.DataFrame,
        events: List[TransientEvent],
        map_rate_table: pd.DataFrame,
        tps_rate_table: pd.DataFrame,
    ) -> Dict[str, plt.Figure]:
        """Create visualization plots."""
        plots = {}
        
        # Plot 1: MAP Rate Enrichment Table
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        ax1.plot(
            map_rate_table['map_rate_kpa_per_sec'],
            map_rate_table['enrichment_percent'],
            'o-',
            linewidth=2,
            markersize=8,
        )
        ax1.set_xlabel('MAP Rate (kPa/sec)', fontsize=12)
        ax1.set_ylabel('Enrichment (%)', fontsize=12)
        ax1.set_title('MAP Rate-Based Enrichment Table', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax1.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        plots['map_rate_enrichment'] = fig1
        
        # Plot 2: TPS Rate Enrichment Table
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        ax2.plot(
            tps_rate_table['tps_rate_percent_per_sec'],
            tps_rate_table['enrichment_percent'],
            'o-',
            linewidth=2,
            markersize=8,
            color='orange',
        )
        ax2.set_xlabel('TPS Rate (%/sec)', fontsize=12)
        ax2.set_ylabel('Enrichment (%)', fontsize=12)
        ax2.set_title('TPS Rate-Based Enrichment Table', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax2.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        plots['tps_rate_enrichment'] = fig2
        
        # Plot 3: Transient Events Timeline
        if events:
            fig3, (ax3a, ax3b, ax3c) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
            
            # RPM and TPS
            ax3a.plot(df['time'], df['rpm'], label='RPM', linewidth=1)
            ax3a.set_ylabel('RPM', fontsize=11)
            ax3a.legend(loc='upper right')
            ax3a.grid(True, alpha=0.3)
            
            # MAP and rates
            ax3b.plot(df['time'], df['map'], label='MAP (kPa)', linewidth=1)
            if 'map_rate' in df.columns:
                ax3b_twin = ax3b.twinx()
                ax3b_twin.plot(df['time'], df['map_rate'], label='MAP Rate', 
                              color='orange', linewidth=1, alpha=0.7)
                ax3b_twin.set_ylabel('MAP Rate (kPa/s)', fontsize=11)
                ax3b_twin.legend(loc='upper right')
            ax3b.set_ylabel('MAP (kPa)', fontsize=11)
            ax3b.legend(loc='upper left')
            ax3b.grid(True, alpha=0.3)
            
            # AFR
            ax3c.plot(df['time'], df['afr'], label='AFR', linewidth=1)
            ax3c.plot(df['time'], df['target_afr'], label='Target AFR', 
                     linestyle='--', linewidth=1, color='red')
            
            # Highlight transient events
            for event in events:
                color = 'green' if event.event_type == 'accel' else 'red'
                alpha = 0.2
                ax3a.axvspan(event.start_time, event.end_time, alpha=alpha, color=color)
                ax3b.axvspan(event.start_time, event.end_time, alpha=alpha, color=color)
                ax3c.axvspan(event.start_time, event.end_time, alpha=alpha, color=color)
            
            ax3c.set_xlabel('Time (sec)', fontsize=12)
            ax3c.set_ylabel('AFR', fontsize=11)
            ax3c.legend(loc='upper right')
            ax3c.grid(True, alpha=0.3)
            
            fig3.suptitle('Transient Events Timeline', fontsize=14, fontweight='bold')
            fig3.tight_layout()
            plots['timeline'] = fig3
        
        return plots
    
    def export_power_vision(self, result: TransientFuelResult, output_path: str) -> None:
        """
        Export results to Power Vision compatible format.
        
        Args:
            result: TransientFuelResult from analysis
            output_path: Path to save the export file
            
        Note:
            This is a simplified export. Full Power Vision integration would require
            their proprietary format specifications.
        """
        with open(output_path, 'w') as f:
            f.write("# DynoAI_3 Transient Fuel Compensation Export\n")
            f.write("# Generated for Power Vision Tuning\n")
            f.write(f"# IAT Reference: {self.iat_reference_c}°C\n")
            f.write(f"# Compensation Factor: {self.compensation_factor}\n")
            
            # Add environmental conditions if present
            if self._env_correction is not None:
                env = self._env_correction
                cond = self.environmental_conditions
                f.write(f"# Environmental Correction: {(env.total_correction-1)*100:+.1f}%\n")
                f.write(f"#   Barometric: {cond.barometric_pressure_inhg:.2f} inHg\n")
                f.write(f"#   Altitude: ~{cond.altitude_ft:.0f} ft\n")
                f.write(f"#   Ambient Temp: {cond.ambient_temp_f:.1f}°F\n")
                f.write(f"#   Humidity: {cond.humidity_percent:.1f}%\n")
                if cond.ect_f:
                    f.write(f"#   ECT: {cond.ect_f:.1f}°F\n")
            f.write("\n")
            
            # IAT Configuration
            f.write("## IAT Compensation Configuration\n")
            f.write(f"Reference Temperature: {self.iat_reference_c}°C\n")
            f.write(f"Density Coefficient: {self.iat_density_coeff} (per °C)\n")
            f.write(f"Wall Wetting Coefficient: {self.iat_wall_wetting_coeff} (per °C)\n")
            f.write("# Cold air (<25°C) increases enrichment due to higher density and wall wetting\n")
            f.write("# Hot air (>25°C) decreases enrichment due to lower density\n\n")
            
            # MAP Rate Table (now includes IAT)
            f.write("## MAP Rate-Based Enrichment (IAT-Corrected)\n")
            f.write(result.map_rate_table.to_csv(index=False))
            f.write("\n")
            
            # TPS Rate Table (now includes IAT)
            f.write("## TPS Rate-Based Enrichment (IAT-Corrected)\n")
            f.write(result.tps_rate_table.to_csv(index=False))
            f.write("\n")
            
            # Wall Wetting Factors
            f.write("## Wall Wetting Compensation Factors (IAT-Adjusted)\n")
            for rpm_range, factor in result.wall_wetting_factor.items():
                f.write(f"{rpm_range}: {factor}\n")
            f.write("\n")
            
            # X-Tau Wall Wetting Parameters
            f.write("## X-Tau Wall Wetting Model Parameters (IAT-Scaled)\n")
            f.write("# X = fraction of fuel that wets port walls (0-1)\n")
            f.write("# Tau = time constant for evaporation (seconds)\n")
            f.write("# Both X and tau are scaled by IAT: cold increases values, hot decreases\n")
            f.write("# Enrichment formula: enrich% = X * tau * (MAP_rate/100) * 100\n\n")
            for params in result.tau_wall_wetting_params:
                f.write(f"{params.rpm_range}:\n")
                f.write(f"  X (wall wetting fraction): {params.x_fraction:.3f}\n")
                f.write(f"  Tau (time constant): {params.tau_seconds:.2f}s\n")
                f.write(f"  Temperature condition: {params.temperature_condition}\n")
            f.write("\n")
            
            # Recommendations
            f.write("## Recommendations\n")
            for rec in result.recommendations:
                f.write(f"- {rec}\n")


if __name__ == "__main__":
    # Example usage
    print("Transient Fuel Compensation Analyzer - Example Usage")
    print("=" * 60)
    
    # Generate synthetic test data
    np.random.seed(42)
    time = np.linspace(0, 30, 1500)  # 30 seconds at 50 Hz
    
    # Simulate acceleration event at t=5-10s
    rpm = np.ones_like(time) * 3000
    rpm[(time >= 5) & (time <= 10)] = 3000 + (time[(time >= 5) & (time <= 10)] - 5) * 800
    
    map_kpa = np.ones_like(time) * 50
    map_kpa[(time >= 5) & (time <= 10)] = 50 + (time[(time >= 5) & (time <= 10)] - 5) * 30
    
    tps = np.ones_like(time) * 20
    tps[(time >= 5) & (time <= 10)] = 20 + (time[(time >= 5) & (time <= 10)] - 5) * 12
    
    # AFR goes lean during accel (simulating inadequate enrichment)
    afr = np.ones_like(time) * 13.0
    afr[(time >= 5) & (time <= 10)] = 13.0 + (time[(time >= 5) & (time <= 10)] - 5) * 0.6
    
    # Add some noise
    afr += np.random.normal(0, 0.1, len(time))
    
    # Create DataFrame
    df = pd.DataFrame({
        'time': time,
        'rpm': rpm,
        'map': map_kpa,
        'tps': tps,
        'afr': afr,
        'iat': np.ones_like(time) * 25,  # 25°C
        'target_afr': np.ones_like(time) * 13.0,
    })
    
    # Analyze
    analyzer = TransientFuelAnalyzer(
        target_afr=13.0,
        map_rate_threshold=50.0,
        tps_rate_threshold=20.0,
    )
    
    result = analyzer.analyze_transients(df)
    
    # Print results
    print(f"\nDetected {len(result.detected_events)} transient events:")
    for i, event in enumerate(result.detected_events, 1):
        print(f"  Event {i}: {event.event_type} ({event.severity}) at t={event.start_time:.1f}s")
        print(f"    Peak MAP rate: {event.peak_map_rate:.1f} kPa/s")
        print(f"    Peak TPS rate: {event.peak_tps_rate:.1f} %/s")
        print(f"    AFR error: {event.afr_error_avg:.2f} (peak: {event.afr_error_peak:.2f})")
    
    print("\nMAP Rate Enrichment Table:")
    print(result.map_rate_table.to_string(index=False))
    
    print("\nWall Wetting Factors:")
    for rpm_range, factor in result.wall_wetting_factor.items():
        print(f"  {rpm_range}: {factor}")
    
    print("\nRecommendations:")
    for rec in result.recommendations:
        print(f"  - {rec}")
    
    print("\n✅ Example completed successfully!")

