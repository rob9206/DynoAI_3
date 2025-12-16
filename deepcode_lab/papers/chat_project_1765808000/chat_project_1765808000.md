# User Coding Requirements

## Project Description
This is a coding project generated from user requirements via chat interface.

## User Requirements

Project: DynoAI_3 - Deterministic Dyno Tuning Platform

Core Principles:
- Deterministic math (same inputs = same outputs, bit-for-bit)
- Automation-first design (headless CLI, batch processing)
- Production safety (conservative defaults, dry-run mode)
- Formal contracts (explicit schemas, units, invariants)

Technology Stack:
- Backend: Python 3.10+, Flask, pandas, numpy, scipy
- Testing: pytest, pytest-asyncio

Coding Standards:
- Type hints for all functions and methods
- Comprehensive docstrings (Google style)
- Unit tests with 80%+ coverage
- Deterministic behavior (no randomness in core logic)
- Conservative error handling

Feature Request: Create Transient Fuel Compensation Module

Module: dynoai/core/transient_fuel.py

Purpose:
Analyze transient engine conditions (acceleration/deceleration) and calculate 
fuel compensation needed for wall-wetting effects and manifold dynamics.

Features:
1. Wall-Wetting Compensation Analysis
   - Calculate fuel film buildup/evaporation during transients
   - Model intake manifold fuel puddling
   - Temperature-dependent evaporation rates

2. MAP Rate-Based Enrichment
   - Analyze manifold pressure rate of change
   - Calculate enrichment for rapid throttle opening
   - Detect boost spike conditions
   - Generate MAP rate vs enrichment tables

3. TPS Rate-Based Enrichment
   - Analyze throttle position rate of change
   - Detect tip-in vs gradual acceleration
   - Calculate TPS rate vs enrichment multipliers
   - Separate tables for opening/closing

4. Deceleration Fuel Cut Analysis
   - Detect decel conditions (negative MAP/TPS rates)
   - Calculate lean-out requirements
   - Prevent flooding on decel
   - Generate decel fuel cut tables

5. Transient Compensation Tables
   - 2D table: MAP rate (delta/sec) vs Base Enrichment %
   - 2D table: TPS rate (delta/sec) vs Base Enrichment %
   - 3D table: RPM x MAP Rate x Enrichment %
   - Export to Power Vision compatible format

Input Format:
- DataFrame with columns: [time, rpm, map, tps, afr, iat, target_afr]
- Sample rate: 50-100 Hz (critical for rate calculations)
- Units: time (seconds), rpm (rev/min), map (kPa), tps (%), afr (ratio), iat (degC)

Output Format:
- TransientFuelResult dataclass with:
  - wall_wetting_factor: Dict[rpm_range, factor]
  - map_rate_table: DataFrame (MAP_rate_kpa_per_sec x enrichment_percent)
  - tps_rate_table: DataFrame (TPS_rate_percent_per_sec x enrichment_percent)
  - transient_3d_table: DataFrame (RPM x MAP_rate x enrichment)
  - decel_fuel_cut_table: DataFrame (RPM x conditions)
  - afr_error_during_transients: List[Tuple[time, error_percent]]
  - recommendations: List[str]
  - plots: Dict[str, matplotlib.Figure]

Key Analysis Methods:
1. detect_transient_events(df) -> List[TransientEvent]
   - Identify accel/decel events
   - Classify severity (mild, moderate, aggressive)
   - Extract event windows for analysis

2. calculate_map_rate_enrichment(df, events) -> DataFrame
   - For each transient event, calculate MAP rate
   - Measure AFR error during transient
   - Correlate error to MAP rate
   - Build enrichment table to correct errors

3. calculate_tps_rate_enrichment(df, events) -> DataFrame
   - Similar to MAP rate but for TPS
   - Separate tip-in from gradual accel
   - Account for gear/load conditions

4. calculate_wall_wetting_compensation(df, events) -> Dict
   - Model fuel film dynamics
   - Temperature correction factors
   - RPM-dependent evaporation

5. generate_power_vision_tables(result) -> Dict[str, bytes]
   - Export to Power Vision .cal format
   - Include all transient compensation tables
   - Add metadata and checksums

Requirements:
- Type hints for all functions (use dataclasses for results)
- Comprehensive docstrings (Google style)
- Deterministic calculations (no random behavior)
- Conservative thresholds (avoid over-enrichment)
- Unit tests with synthetic transient data
- Example usage showing full workflow
- Integration with existing DynoAI_3 patterns
- Handle edge cases (noisy sensors, incomplete data)
- Validate input data quality

Integration Points:
- Should work with JetDrive data format
- Compatible with existing VE correction workflow
- Export format matches Power Vision expectations
- Can be called from Flask API endpoint
- CLI interface for batch processing

Example Usage in Docstring:
```python
# Load dyno log with transient events
df = pd.read_csv('dyno_run_with_accel.csv')

# Initialize analyzer
analyzer = TransientFuelAnalyzer(
    target_afr=13.0,
    map_rate_threshold=50.0,  # kPa/sec
    tps_rate_threshold=20.0,  # %/sec
)

# Analyze transients
result = analyzer.analyze_transients(df)

# Review recommendations
for rec in result.recommendations:
    print(rec)

# Export to Power Vision
pv_tables = analyzer.export_power_vision(result)
with open('transient_comp.cal', 'wb') as f:
    f.write(pv_tables['transient_compensation'])

# Plot results
result.plots['map_rate_enrichment'].savefig('map_rate.png')
```

Test Requirements:
- Test with synthetic data (known transient events)
- Test rate calculations (verify derivatives)
- Test edge cases (very fast/slow transients)
- Test decel handling
- Test export format validity
- Test determinism (same input = same output)
- Mock matplotlib for faster tests

Output Location: dynoai/core/transient_fuel.py
Test Location: tests/test_transient_fuel.py

Please generate production-ready code that can be directly integrated into DynoAI_3.
Include comprehensive docstrings, type hints, and unit tests.


## Generated Implementation Plan
The following implementation plan was generated by the AI chat planning agent:

```yaml
```yaml
project_plan:
  title: "DynoAI_3 - Deterministic Dyno Tuning Platform"
  description: "A platform for deterministic engine tuning, featuring a Transient Fuel Compensation Module."
  project_type: "tool"

  file_structure: |
    dynoai/
    ├── core/
    │   ├── __init__.py
    │   └── transient_fuel.py     # Core module for Transient Fuel Compensation
    ├── cli/
    │   ├── __init__.py
    │   └── interface.py          # CLI interface
    ├── api/
    │   ├── __init__.py
    │   └── endpoints.py          # Flask API endpoints for integration
    ├── tests/
    │   ├── __init__.py
    │   └── test_transient_fuel.py# Unit tests for transient_fuel.py
    ├── requirements.txt          # Dependencies
    ├── README.md                 # Basic documentation
    └── setup.py                  # Package setup configuration

  implementation_steps:
    1. "Set up the project structure and initialize Python modules."
    2. "Develop the transient_fuel.py module with core features like wall-wetting analysis, MAP and TPS rate enrichment, and deceleration fuel cut."
    3. "Implement the CLI and API interfaces for integration with existing systems and batch processing capabilities."
    4. "Create comprehensive unit tests in test_transient_fuel.py to ensure accuracy of calculations and robustness against edge cases."

  dependencies:
    required_packages:
      - "Python>=3.10"
      - "Flask>=2.0"
      - "pandas>=1.3"
      - "numpy>=1.21"
      - "scipy>=1.7"
      - "pytest>=7.0"
      - "pytest-asyncio>=0.16"
      - "matplotlib>=3.4"
    optional_packages:
      - "numba: Speed up computation-heavy sections like rate calculations"
    setup_commands:
      - "python -m venv venv"
      - "source venv/bin/activate"
      - "pip install -r requirements.txt"

  tech_stack:
    language: "Python"
    frameworks: ["Flask"]
    key_libraries: ["pandas", "numpy", "scipy", "matplotlib", "pytest"]

  main_features:
    - "Wall-Wetting Compensation Analysis"
    - "MAP and TPS Rate-Based Enrichment"
    - "Deceleration Fuel Cut Analysis"
    - "Export transient compensation tables to Power Vision format"
```

This implementation plan focuses on creating a deterministic, safe, and automated transient fuel compensation module within the DynoAI_3 platform. It leverages a structured project setup and utilizes modern Python libraries and tools to achieve high accuracy and reliability. The focus is on building robust, well-tested features that integrate seamlessly with the existing infrastructure, ensuring compatibility with all specified requirements and tests.
```

## Project Metadata
- **Input Type**: Chat Input
- **Generation Method**: AI Chat Planning Agent
- **Timestamp**: 1765808000
