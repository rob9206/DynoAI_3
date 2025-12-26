# DynoAI_3 <-> DeepCode Integration Guide

This guide explains how to use DeepCode to accelerate DynoAI_3 development.

## 🚀 Quick Start

### Prerequisites

1. **DeepCode installed** at `C:\Users\dawso\OneDrive\DeepCode\DeepCode`
2. **API keys configured** in DeepCode's `mcp_agent.secrets.yaml`
3. **Python 3.10+** with asyncio support

### Running the Integration

```powershell
cd C:\dev\dynoai_3
python deepcode_integration.py
```

## 📋 Interactive Menu

The integration script provides an interactive menu with these options:

### 1. 🔧 New Analysis Module
Generate core analysis algorithms for DynoAI_3:
- Boost pressure analysis
- Transient fuel compensation
- Cylinder temperature modeling
- Advanced knock detection
- Custom algorithms

**Example:**
```
Module name: boost_analyzer
Description: Analyze boost pressure curves and detect wastegate issues
```

### 2. 🌐 API Endpoint
Generate Flask REST API endpoints:
- New analysis endpoints
- Data export endpoints
- Hardware integration endpoints
- Admin/monitoring endpoints

**Example:**
```
Endpoint: /api/boost/analyze
Method: POST
Purpose: Analyze boost pressure data from uploaded CSV
```

### 3. 🎨 Frontend Component
Generate React/TypeScript UI components:
- Data visualizations
- Interactive gauges
- Configuration panels
- Dashboard widgets

**Example:**
```
Component: BoostPressureGauge
Purpose: Real-time boost pressure display with peak hold
```

### 4. 📝 Tests for Existing Module
Generate comprehensive test suites:
- Unit tests
- Integration tests
- Property-based tests
- Edge case coverage

**Example:**
```
Module: dynoai/core/ve_math.py
```

### 5. 📚 Documentation
Generate technical documentation:
- API documentation
- Algorithm explanations
- Integration guides
- User manuals

**Example:**
```
Topic: Boost Analysis System
```

### 6. 💡 Custom Feature
Free-form feature generation - describe anything you need!

## 🎯 Example Use Cases

### Use Case 1: New Analysis Algorithm

```python
from deepcode_integration import DynoAI3DeepCodeIntegration
import asyncio

async def generate_boost_analyzer():
    integrator = DynoAI3DeepCodeIntegration()
    
    await integrator.generate_feature("""
    Create boost pressure analysis module for DynoAI_3:
    
    Module: dynoai/core/boost_analyzer.py
    
    Features:
    - Parse boost pressure data from dyno logs
    - Calculate boost-by-RPM curves
    - Detect boost leaks (pressure drop analysis)
    - Compare actual vs target boost
    - Generate boost correction recommendations
    - Export results to CSV and matplotlib plots
    
    Input: DataFrame with columns [time, rpm, map, boost_psi, throttle_pos]
    Output: BoostAnalysisResult with metrics and recommendations
    
    Include:
    - Type hints for all functions
    - Comprehensive docstrings
    - Unit tests with sample data
    - Example usage in main block
    """)

asyncio.run(generate_boost_analyzer())
```

### Use Case 2: API Endpoint

```python
await integrator.generate_api_endpoint("""
Create endpoint: POST /api/jetdrive/boost-analysis

Purpose: Analyze boost pressure data from JetDrive capture

Request Body:
{
  "run_id": "string",
  "target_boost_psi": 15.0,
  "tolerance_psi": 1.0
}

Response:
{
  "status": "success",
  "boost_curve": [...],
  "leak_detected": false,
  "recommendations": [...]
}

Include:
- Input validation
- Error handling
- Rate limiting
- OpenAPI documentation
- Unit tests
""")
```

### Use Case 3: Frontend Component

```python
await integrator.generate_frontend_component("""
Component: BoostPressureChart

Purpose: Interactive boost pressure visualization

Features:
- Line chart showing boost vs RPM
- Target boost overlay
- Highlight leak zones in red
- Zoom/pan controls
- Export to PNG
- Responsive design

Props:
- boostData: Array<{rpm: number, boost: number}>
- targetBoost: number
- onZoneClick?: (rpm: number) => void

Use Recharts library for charting
""")
```

## 🔧 Advanced Usage

### Programmatic API

```python
from deepcode_integration import DynoAI3DeepCodeIntegration

async def main():
    integrator = DynoAI3DeepCodeIntegration(
        output_base_dir=r"C:\dev\dynoai_3\generated_features"
    )
    
    # Generate with code reference indexing (slower but more context-aware)
    result = await integrator.generate_feature(
        feature_description="...",
        enable_indexing=True,
        fast_mode=False
    )
    
    print(result)
```

### Batch Generation

```python
features = [
    "Boost pressure analyzer",
    "Transient fuel compensation",
    "Cylinder temperature modeling"
]

for feature in features:
    await integrator.generate_feature(f"""
    Create {feature} module for DynoAI_3
    Location: dynoai/core/{feature.lower().replace(' ', '_')}.py
    Include full implementation with tests
    """)
```

## 📁 Output Structure

Generated code appears in:
```
C:\Users\dawso\OneDrive\DeepCode\DeepCode\deepcode_lab\papers\chat_project_*/
└── generate_code/
    ├── dynoai/
    │   └── core/
    │       └── your_new_module.py
    ├── tests/
    │   └── test_your_new_module.py
    └── docs/
        └── your_documentation.md
```

**Integration Steps:**
1. Review generated code in `deepcode_lab/papers/chat_project_*/generate_code/`
2. Copy relevant files to DynoAI_3 directories
3. Run tests: `pytest tests/test_your_new_module.py`
4. Integrate into main codebase

## 💡 Tips for Best Results

### 1. Be Specific
❌ Bad: "Create a boost analyzer"
✅ Good: "Create boost pressure analysis module with leak detection, target comparison, and CSV export"

### 2. Provide Context
Include:
- Input data format
- Expected output
- Integration points
- Coding standards

### 3. Specify File Locations
```
Module: dynoai/core/boost_analyzer.py
Tests: tests/test_boost_analyzer.py
```

### 4. Request Tests and Docs
Always ask for:
- Unit tests
- Type hints
- Docstrings
- Example usage

### 5. Follow DynoAI_3 Patterns
Mention:
- Deterministic behavior
- Conservative error handling
- Production safety
- Existing code patterns

## 🐛 Troubleshooting

### Issue: "Could not import DeepCode modules"
**Solution:** Verify DeepCode path in script (line 16):
```python
DEEPCODE_PATH = r"C:\Users\dawso\OneDrive\DeepCode\DeepCode"
```

### Issue: "API key not configured"
**Solution:** Configure API keys in DeepCode:
```powershell
cd C:\Users\dawso\OneDrive\DeepCode\DeepCode
# Edit mcp_agent.secrets.yaml with your API keys
```

### Issue: Generation takes too long
**Solution:** Use fast mode (default):
```python
await integrator.generate_feature(
    feature_description="...",
    fast_mode=True  # Skips GitHub reference discovery
)
```

### Issue: Generated code doesn't match DynoAI_3 style
**Solution:** Add more context in your request:
```python
"""
... your feature description ...

Requirements:
- Follow DynoAI_3 coding standards
- Use type hints
- Deterministic behavior
- Conservative error handling
- Match existing code patterns in dynoai/core/
"""
```

## 📚 Examples Library

### Example 1: Transient Fuel Compensation
```python
await integrator.generate_feature("""
Create transient fuel compensation module:

Module: dynoai/core/transient_fuel.py

Features:
- Calculate wall-wetting compensation
- MAP rate-based enrichment
- TPS rate-based enrichment
- Export to Power Vision format

Input: DataFrame with [time, rpm, map, tps, afr]
Output: Transient compensation table (RPM × MAP rate)
""")
```

### Example 2: Advanced Visualization
```python
await integrator.generate_frontend_component("""
Component: VE3DSurfaceViewer

Purpose: 3D surface plot of VE table

Features:
- Interactive 3D visualization (Three.js)
- RPM × MAP × VE% surface
- Color gradient for correction factors
- Rotate, zoom, pan controls
- Highlight low-coverage cells
- Export to PNG

Props:
- veData: VETable
- corrections?: VETable
- onCellClick?: (rpm, map) => void
""")
```

### Example 3: Hardware Integration
```python
await integrator.generate_feature("""
Create Power Core USB integration:

Module: integrations/powercore/usb_interface.py

Features:
- Connect to Power Core via USB/serial
- Read live VE tables from ECU
- Write VE corrections to ECU
- Real-time AFR monitoring
- Safety limits (±7% max change)
- Rollback capability
- CLI and API interfaces

Use pyserial for communication
Include comprehensive error handling
""")
```

## 🎓 Learning Resources

- **DeepCode Documentation**: `C:\Users\dawso\OneDrive\DeepCode\DeepCode\README.md`
- **DynoAI_3 Architecture**: `C:\dev\dynoai_3\docs\DYNOAI_ARCHITECTURE_OVERVIEW.md`
- **Coding Standards**: `C:\dev\dynoai_3\CONTRIBUTING.md`

## 🤝 Contributing

Generated code should be:
1. Reviewed before integration
2. Tested thoroughly
3. Documented
4. Committed with clear messages

## 📞 Support

- DynoAI_3 Issues: https://github.com/rob9206/DynoAI_3/issues
- DeepCode Issues: https://github.com/HKUDS/DeepCode/issues

---

**Happy Coding! 🚀**

