# 🚀 Quick Start: DynoAI_3 + DeepCode Integration

Get started with AI-powered feature generation for DynoAI_3 in 5 minutes!

## ✅ Prerequisites Check

Before starting, verify:

```powershell
# 1. Check Python version (need 3.10+)
python --version

# 2. Check DeepCode is accessible
cd C:\Users\dawso\OneDrive\DeepCode\DeepCode
python -c "import workflows.agent_orchestration_engine; print('✅ DeepCode OK')"

# 3. Check API keys configured
# Edit: C:\Users\dawso\OneDrive\DeepCode\DeepCode\mcp_agent.secrets.yaml
# Ensure OPENAI_API_KEY or ANTHROPIC_API_KEY is set
```

## 🎯 Method 1: Interactive Menu (Easiest)

```powershell
cd C:\dev\dynoai_3
python deepcode_integration.py
```

Then follow the on-screen menu:
1. Choose what to generate (module, API, component, etc.)
2. Answer a few questions
3. Wait for DeepCode to generate the code
4. Review and integrate!

## 🎨 Method 2: Run Examples

```powershell
cd C:\dev\dynoai_3
python example_deepcode_usage.py
```

Choose from pre-built examples:
- Boost pressure analyzer
- API endpoints
- React components
- Documentation
- Test suites

## 💻 Method 3: Programmatic (Advanced)

Create your own script:

```python
# my_feature_generator.py
import asyncio
from deepcode_integration import DynoAI3DeepCodeIntegration

async def main():
    integrator = DynoAI3DeepCodeIntegration()
    
    await integrator.generate_feature("""
    Create a [YOUR FEATURE HERE] for DynoAI_3:
    
    Module: dynoai/core/my_feature.py
    
    Features:
    - Feature 1
    - Feature 2
    - Feature 3
    
    Include tests and documentation.
    """)

asyncio.run(main())
```

Then run:
```powershell
python my_feature_generator.py
```

## 📁 Finding Generated Code

After generation completes, find your code at:

```
C:\Users\dawso\OneDrive\DeepCode\DeepCode\deepcode_lab\papers\chat_project_[TIMESTAMP]\generate_code\
```

Example:
```
deepcode_lab\papers\chat_project_1763601012\generate_code\
├── dynoai\
│   └── core\
│       └── boost_analyzer.py    ← Your new module!
├── tests\
│   └── test_boost_analyzer.py   ← Tests
└── docs\
    └── boost_analyzer.md        ← Documentation
```

## 🔄 Integration Steps

1. **Review** the generated code
2. **Copy** to DynoAI_3 directories:
   ```powershell
   # Example
   copy deepcode_lab\papers\chat_project_*\generate_code\dynoai\core\*.py dynoai\core\
   copy deepcode_lab\papers\chat_project_*\generate_code\tests\*.py tests\
   ```
3. **Test** the new code:
   ```powershell
   pytest tests/test_boost_analyzer.py -v
   ```
4. **Integrate** into your workflow

## 💡 First Feature Ideas

Not sure what to generate? Try these:

### 1. Transient Fuel Compensation
```python
await integrator.generate_feature("""
Create transient fuel compensation module for DynoAI_3:
- Analyze acceleration enrichment needs
- Calculate wall-wetting compensation
- Generate TPS-rate-based fuel multipliers
- Export to Power Vision format
""")
```

### 2. Advanced Knock Detection
```python
await integrator.generate_feature("""
Create advanced knock detection module:
- Analyze knock sensor data by RPM/MAP zones
- Detect knock patterns
- Calculate safe spark advance limits
- Generate spark correction table
""")
```

### 3. Real-Time Dashboard
```python
await integrator.generate_frontend_component("""
Create real-time monitoring dashboard component:
- Live gauges for RPM, MAP, AFR, TPS
- Real-time VE correction heatmap
- Alert system for out-of-range values
- WebSocket connection for live data
""")
```

## ⚡ Tips for Success

### ✅ DO:
- Be specific about requirements
- Mention file locations
- Request tests and documentation
- Specify input/output formats
- Reference DynoAI_3 standards

### ❌ DON'T:
- Be vague ("make it better")
- Forget to specify file paths
- Skip test requirements
- Ignore existing patterns
- Request multiple unrelated features at once

## 🐛 Troubleshooting

### "Could not import DeepCode modules"
**Fix:** Check the path in `deepcode_integration.py` line 16:
```python
DEEPCODE_PATH = r"C:\Users\dawso\OneDrive\DeepCode\DeepCode"
```

### "API key not configured"
**Fix:** Edit DeepCode's secrets file:
```powershell
notepad C:\Users\dawso\OneDrive\DeepCode\DeepCode\mcp_agent.secrets.yaml
```
Add your API key:
```yaml
openai:
  api_key: "sk-..."
```

### Generation is slow
**Fix:** Use fast mode (default). If you enabled indexing, disable it:
```python
await integrator.generate_feature(
    feature_description="...",
    fast_mode=True  # ← This is default
)
```

### Generated code doesn't match DynoAI_3 style
**Fix:** Add more context to your request:
```python
"""
... your feature ...

Requirements:
- Follow DynoAI_3 coding standards
- Use type hints
- Deterministic behavior
- Match patterns in dynoai/core/
"""
```

## 📚 Next Steps

1. **Read the full guide**: `DEEPCODE_INTEGRATION_README.md`
2. **Try the examples**: `python example_deepcode_usage.py`
3. **Generate your first feature**: `python deepcode_integration.py`
4. **Explore DeepCode docs**: `C:\Users\dawso\OneDrive\DeepCode\DeepCode\README.md`

## 🎓 Learning Path

1. **Day 1**: Run interactive menu, generate a simple module
2. **Day 2**: Try the examples, understand the workflow
3. **Day 3**: Generate a real feature you need
4. **Day 4**: Create custom generation scripts
5. **Day 5**: Master advanced features (indexing, batch generation)

## 🤝 Getting Help

- **DynoAI_3 Issues**: https://github.com/rob9206/DynoAI_3/issues
- **DeepCode Docs**: `C:\Users\dawso\OneDrive\DeepCode\DeepCode\README.md`
- **Full Integration Guide**: `DEEPCODE_INTEGRATION_README.md`

---

**Ready? Let's generate some code! 🚀**

```powershell
python deepcode_integration.py
```

