"""
Example Usage of DynoAI_3 <-> DeepCode Integration

This script demonstrates various ways to use DeepCode to generate
features for DynoAI_3.

Run this to see DeepCode in action!
"""

import asyncio
from deepcode_integration import DynoAI3DeepCodeIntegration


async def example_1_boost_analyzer():
    """Example 1: Generate a boost pressure analysis module."""
    print("\n" + "=" * 70)
    print("📊 Example 1: Boost Pressure Analyzer")
    print("=" * 70 + "\n")

    integrator = DynoAI3DeepCodeIntegration()

    await integrator.generate_feature(
        """
Create a boost pressure analysis module for DynoAI_3:

Module: dynoai/core/boost_analyzer.py

Purpose:
Analyze boost pressure data from dyno runs to detect issues and optimize
turbocharger/supercharger performance.

Features:
1. Parse boost pressure data from CSV logs
2. Calculate boost-by-RPM curves
3. Detect boost leaks (pressure drop analysis)
4. Compare actual vs target boost
5. Identify wastegate control issues
6. Generate boost correction recommendations
7. Export results to CSV and matplotlib plots

Input Format:
- DataFrame with columns: [time, rpm, map, boost_psi, throttle_pos, gear]
- Sample rate: 10-100 Hz
- Units: time (seconds), rpm (rev/min), boost_psi (psi gauge)

Output Format:
- BoostAnalysisResult dataclass with:
  - boost_curve: List[Tuple[rpm, boost_psi]]
  - leak_detected: bool
  - leak_severity: float (0-1)
  - target_deviation: float (average psi difference)
  - recommendations: List[str]
  - plots: Dict[str, matplotlib.Figure]

Requirements:
- Type hints for all functions
- Comprehensive docstrings (Google style)
- Unit tests with synthetic data
- Example usage in __main__ block
- Deterministic calculations
- Conservative thresholds (avoid false positives)

Integration:
- Should integrate with existing DynoAI_3 analysis pipeline
- Compatible with JetDrive data format
- Export to Power Vision compatible format
"""
    )


async def example_2_api_endpoint():
    """Example 2: Generate a REST API endpoint."""
    print("\n" + "=" * 70)
    print("🌐 Example 2: Boost Analysis API Endpoint")
    print("=" * 70 + "\n")

    integrator = DynoAI3DeepCodeIntegration()

    await integrator.generate_api_endpoint(
        """
Create Flask API endpoint for boost pressure analysis:

Endpoint: POST /api/boost/analyze
Location: api/routes/boost.py

Purpose:
Analyze boost pressure data from uploaded dyno log and return
comprehensive analysis results.

Request Body:
{
  "run_id": "string (optional, auto-generated if not provided)",
  "csv_data": "string (base64 encoded CSV) OR file upload",
  "target_boost_psi": "number (default: 15.0)",
  "tolerance_psi": "number (default: 1.0)",
  "detect_leaks": "boolean (default: true)"
}

Response (200 OK):
{
  "status": "success",
  "run_id": "boost_analysis_12345",
  "results": {
    "boost_curve": [[rpm, boost], ...],
    "peak_boost": 18.5,
    "average_boost": 16.2,
    "leak_detected": false,
    "target_deviation": 1.2,
    "recommendations": [
      "Boost control is within tolerance",
      "Consider raising target by 2 psi"
    ]
  },
  "plots": {
    "boost_curve_url": "/api/download/boost_analysis_12345/boost_curve.png",
    "deviation_heatmap_url": "/api/download/boost_analysis_12345/deviation.png"
  }
}

Response (400 Bad Request):
{
  "status": "error",
  "message": "Invalid CSV format: missing 'boost_psi' column"
}

Response (500 Internal Server Error):
{
  "status": "error",
  "message": "Analysis failed: insufficient data points"
}

Requirements:
- Input validation using jsonschema
- File upload support (multipart/form-data)
- Rate limiting (10 requests/minute)
- Error handling with proper HTTP status codes
- OpenAPI/Swagger documentation
- Unit tests using Flask test client
- Integration with boost_analyzer.py module
- Save results to runs/ directory
- Background processing for large files (optional)

Security:
- Validate file size (max 10MB)
- Sanitize file names
- Check CSV for malicious content
"""
    )


async def example_3_frontend_component():
    """Example 3: Generate a React component."""
    print("\n" + "=" * 70)
    print("🎨 Example 3: Boost Pressure Gauge Component")
    print("=" * 70 + "\n")

    integrator = DynoAI3DeepCodeIntegration()

    await integrator.generate_frontend_component(
        """
Create React/TypeScript component for boost pressure visualization:

Component: BoostPressureGauge
Location: frontend/src/components/BoostPressureGauge.tsx

Purpose:
Real-time boost pressure gauge with peak hold and warning zones.

Props:
interface BoostPressureGaugeProps {
  currentBoost: number;        // Current boost in psi
  targetBoost?: number;        // Target boost (optional)
  maxBoost?: number;           // Max scale (default: 25 psi)
  warningThreshold?: number;   // Yellow zone (default: 20 psi)
  dangerThreshold?: number;    // Red zone (default: 22 psi)
  showPeakHold?: boolean;      // Show peak boost indicator
  animated?: boolean;          // Smooth needle animation
  size?: 'small' | 'medium' | 'large';
  theme?: 'dark' | 'light';
  onOverboost?: (boost: number) => void;
}

Features:
1. Circular gauge with needle indicator
2. Color zones: green (safe), yellow (warning), red (danger)
3. Digital readout of current boost
4. Peak hold indicator (stays at max boost)
5. Target boost marker line
6. Smooth needle animation (CSS transitions)
7. Responsive sizing
8. Dark/light theme support
9. Overboost callback when exceeding danger threshold

Visual Design:
- Gauge range: -5 to maxBoost psi
- Tick marks every 5 psi
- Large digital display in center
- "BOOST" label at bottom
- "PSI" unit label
- Peak hold as small triangle marker
- Target as dashed line

Technical Requirements:
- TypeScript with strict types
- React 18 functional component
- CSS modules or styled-components
- Responsive (scales with container)
- 60 FPS animation performance
- Accessible (ARIA labels)
- Unit tests with React Testing Library
- Storybook story with controls

Styling:
- Match DynoAI_3 dark theme
- Use CSS variables for colors
- Smooth transitions
- No external gauge libraries (custom SVG)

Example Usage:
```tsx
<BoostPressureGauge
  currentBoost={15.5}
  targetBoost={15.0}
  maxBoost={25}
  showPeakHold={true}
  size="large"
  theme="dark"
  onOverboost={(boost) => console.warn(`Overboost: ${boost} psi`)}
/>
```
"""
    )


async def example_4_documentation():
    """Example 4: Generate documentation."""
    print("\n" + "=" * 70)
    print("📚 Example 4: Boost Analysis Documentation")
    print("=" * 70 + "\n")

    integrator = DynoAI3DeepCodeIntegration()

    await integrator.generate_documentation(
        """
Create comprehensive documentation for DynoAI_3 Boost Analysis System

Topic: Boost Pressure Analysis

Sections to include:

1. Overview
   - What is boost analysis?
   - Why is it important for tuning?
   - How does DynoAI_3 analyze boost?

2. Theory and Algorithms
   - Boost pressure fundamentals
   - Leak detection algorithm
   - Target deviation calculation
   - Statistical methods used

3. Data Requirements
   - Required CSV columns
   - Sample rate recommendations
   - Data quality considerations
   - Example data format

4. Using the Boost Analyzer
   - Web UI workflow
   - CLI usage examples
   - API integration examples
   - Interpreting results

5. Configuration
   - Target boost settings
   - Tolerance thresholds
   - Leak detection sensitivity
   - Advanced options

6. Troubleshooting
   - Common issues and solutions
   - Data quality problems
   - False positive leaks
   - Integration errors

7. API Reference
   - Endpoint documentation
   - Request/response schemas
   - Error codes
   - Rate limits

8. Examples
   - Basic boost analysis
   - Detecting boost leaks
   - Comparing multiple runs
   - Exporting results

9. Best Practices
   - Data collection tips
   - Interpretation guidelines
   - Safety considerations
   - Performance optimization

10. Advanced Topics
    - Custom target curves
    - Multi-stage boost control
    - Integration with other systems
    - Batch processing

Format: Markdown with code examples, diagrams (mermaid), and screenshots
Output: docs/boost_analysis_guide.md
"""
    )


async def example_5_tests():
    """Example 5: Generate tests for existing module."""
    print("\n" + "=" * 70)
    print("🧪 Example 5: Generate Tests for VE Math Module")
    print("=" * 70 + "\n")

    integrator = DynoAI3DeepCodeIntegration()

    await integrator.generate_tests("dynoai/core/ve_math.py")


async def main():
    """Run all examples (or choose specific ones)."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "DynoAI_3 <-> DeepCode Examples" + " " * 23 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    print("This script demonstrates various DeepCode integration capabilities.")
    print()
    print("Choose an example to run:")
    print()
    print("1. 📊 Boost Pressure Analyzer (Core Module)")
    print("2. 🌐 Boost Analysis API Endpoint")
    print("3. 🎨 Boost Pressure Gauge (React Component)")
    print("4. 📚 Boost Analysis Documentation")
    print("5. 🧪 Generate Tests for VE Math Module")
    print("6. 🚀 Run All Examples (will take a while!)")
    print("7. 🚪 Exit")
    print()

    choice = input("Enter your choice (1-7): ").strip()

    examples = {
        "1": example_1_boost_analyzer,
        "2": example_2_api_endpoint,
        "3": example_3_frontend_component,
        "4": example_4_documentation,
        "5": example_5_tests,
    }

    if choice in examples:
        await examples[choice]()
        print("\n✅ Example completed!")
        print(
            f"\n📁 Check output in: C:\\Users\\dawso\\OneDrive\\DeepCode\\DeepCode\\deepcode_lab\\papers\\"
        )
    elif choice == "6":
        print("\n🚀 Running all examples...")
        for name, example_func in examples.items():
            await example_func()
            print(f"\n✅ Example {name} completed!\n")
        print("\n🎉 All examples completed!")
    elif choice == "7":
        print("\n👋 Goodbye!")
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
