"""
DynoAI_3 <-> DeepCode Integration Script

This script provides a seamless integration between DynoAI_3 and DeepCode,
allowing you to use DeepCode's AI-powered code generation capabilities to
rapidly develop new features for the DynoAI_3 platform.

Usage:
    python deepcode_integration.py

Author: DeepCode Integration
Date: 2025-01-15
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add DeepCode to Python path
DEEPCODE_PATH = r"C:\Users\dawso\OneDrive\DeepCode\DeepCode"
if DEEPCODE_PATH not in sys.path:
    sys.path.insert(0, DEEPCODE_PATH)

try:
    from workflows.agent_orchestration_engine import (
        execute_chat_based_planning_pipeline,
    )
    from utils.simple_llm_logger import SimpleLLMLogger
except ImportError as e:
    print(f"❌ Error: Could not import DeepCode modules.")
    print(f"   Make sure DeepCode is installed at: {DEEPCODE_PATH}")
    print(f"   Error details: {e}")
    sys.exit(1)


class DynoAI3DeepCodeIntegration:
    """
    Integration layer between DynoAI_3 and DeepCode for automated feature generation.

    This class provides methods to generate new features, modules, tests, and
    documentation for DynoAI_3 using DeepCode's multi-agent system.
    """

    def __init__(self, output_base_dir: Optional[str] = None):
        """
        Initialize the integration.

        Args:
            output_base_dir: Base directory for DeepCode outputs.
                           Defaults to C:\dev\dynoai_3\deepcode_generated
        """
        self.logger = SimpleLLMLogger()

        if output_base_dir:
            self.output_dir = Path(output_base_dir)
        else:
            self.output_dir = Path(r"C:\dev\dynoai_3\deepcode_generated")

        self.output_dir.mkdir(exist_ok=True)

        # Ensure config files are available in current directory
        self._setup_config_files()

        print("=" * 70)
        print("🚀 DynoAI_3 <-> DeepCode Integration")
        print("=" * 70)
        print(f"📁 Output directory: {self.output_dir}")
        print(f"🧠 DeepCode path: {DEEPCODE_PATH}")
        print()

    def _setup_config_files(self):
        """Ensure DeepCode config files are available in the working directory."""
        import shutil

        deepcode_secrets = Path(DEEPCODE_PATH) / "mcp_agent.secrets.yaml"
        deepcode_config = Path(DEEPCODE_PATH) / "mcp_agent.config.yaml"

        local_secrets = Path("mcp_agent.secrets.yaml")
        local_config = Path("mcp_agent.config.yaml")

        # Copy secrets file if it doesn't exist locally
        if deepcode_secrets.exists() and not local_secrets.exists():
            shutil.copy(deepcode_secrets, local_secrets)
            print(f"✅ Copied config: {local_secrets}")

        # Copy config file if it doesn't exist locally
        if deepcode_config.exists() and not local_config.exists():
            shutil.copy(deepcode_config, local_config)
            print(f"✅ Copied config: {local_config}")

    def _build_dynoai3_context(self) -> str:
        """Build context about DynoAI_3 for better code generation."""
        return """
Project: DynoAI_3 - Deterministic Dyno Tuning Platform

Core Principles:
- Deterministic math (same inputs = same outputs, bit-for-bit)
- Automation-first design (headless CLI, batch processing)
- Production safety (conservative defaults, dry-run mode)
- Formal contracts (explicit schemas, units, invariants)
- World-class reliability

Technology Stack:
- Backend: Python 3.10+, Flask, pandas, numpy, scipy
- Frontend: React 18, TypeScript, Vite
- Database: SQLite (development), PostgreSQL (production)
- Testing: pytest, pytest-asyncio

Coding Standards:
- Type hints for all functions and methods
- Comprehensive docstrings (Google style)
- Unit tests with 80%+ coverage
- Deterministic behavior (no randomness in core logic)
- Conservative error handling
- SHA-256 verification for critical operations

Project Structure:
- api/ - Flask REST API endpoints
- dynoai/core/ - Core analysis algorithms
- dynoai/clients/ - External integrations
- frontend/src/ - React/TypeScript UI
- scripts/ - CLI tools
- tests/ - Test suite
- docs/ - Documentation

Key Modules:
- ve_math.py - VE correction calculations
- ve_operations.py - Apply/rollback system
- cylinder_balancing.py - Per-cylinder analysis
- decel_management.py - Deceleration fuel management
- knock_optimization.py - Knock detection and spark control
"""

    async def generate_feature(
        self,
        feature_description: str,
        enable_indexing: bool = False,
        fast_mode: bool = True,
    ) -> str:
        """
        Generate a new feature for DynoAI_3 using DeepCode.

        Args:
            feature_description: Detailed description of the feature to generate
            enable_indexing: Enable code reference indexing (slower but more context-aware)
            fast_mode: Use fast mode (skip GitHub reference discovery)

        Returns:
            str: Summary of the generation result
        """
        print("=" * 70)
        print("🎯 Feature Generation Request")
        print("=" * 70)
        print(f"Description:\n{feature_description}\n")
        print(f"⚡ Fast mode: {fast_mode}")
        print(f"🔍 Indexing: {enable_indexing}")
        print("=" * 70)
        print()

        # Build enhanced prompt with DynoAI_3 context
        enhanced_prompt = f"""{self._build_dynoai3_context()}

Feature Request:
{feature_description}

Requirements:
1. Follow DynoAI_3 coding standards (type hints, docstrings)
2. Maintain deterministic behavior where applicable
3. Include comprehensive unit tests
4. Add inline documentation
5. Consider production safety
6. Integrate with existing DynoAI_3 architecture
7. Export functions/classes for easy import

Please generate production-ready code that can be directly integrated into DynoAI_3.
"""

        def progress_callback(percent: int, message: str):
            """Display progress updates."""
            print(f"[{percent:3d}%] {message}")

        try:
            result = await execute_chat_based_planning_pipeline(
                user_input=enhanced_prompt,
                logger=self.logger,
                progress_callback=progress_callback,
                enable_indexing=enable_indexing,
            )

            print("\n" + "=" * 70)
            print("✅ Feature Generation Complete!")
            print("=" * 70)
            print(f"\n{result}\n")

            return result

        except Exception as e:
            print("\n" + "=" * 70)
            print("❌ Feature Generation Failed")
            print("=" * 70)
            print(f"Error: {e}\n")
            raise

    async def generate_tests(self, module_path: str) -> str:
        """
        Generate comprehensive tests for an existing DynoAI_3 module.

        Args:
            module_path: Path to the module to test (e.g., 'dynoai/core/ve_math.py')

        Returns:
            str: Summary of test generation
        """
        return await self.generate_feature(
            f"""
Create comprehensive test suite for DynoAI_3 module: {module_path}

Requirements:
- Unit tests for all public functions/classes
- Edge case testing
- Property-based tests where applicable
- Mock external dependencies
- Test deterministic behavior
- 90%+ code coverage
- Use pytest and pytest-asyncio
- Follow DynoAI_3 test conventions

Output location: tests/test_{Path(module_path).stem}.py
"""
        )

    async def generate_documentation(self, topic: str) -> str:
        """
        Generate documentation for DynoAI_3.

        Args:
            topic: Documentation topic or module to document

        Returns:
            str: Summary of documentation generation
        """
        return await self.generate_feature(
            f"""
Create comprehensive documentation for DynoAI_3: {topic}

Requirements:
- Clear, technical writing
- Code examples with explanations
- API reference if applicable
- Usage examples
- Troubleshooting section
- Markdown format
- Diagrams where helpful (mermaid syntax)

Output location: docs/{topic.lower().replace(' ', '_')}.md
"""
        )

    async def generate_api_endpoint(self, endpoint_spec: str) -> str:
        """
        Generate a new Flask API endpoint for DynoAI_3.

        Args:
            endpoint_spec: Specification of the API endpoint

        Returns:
            str: Summary of endpoint generation
        """
        return await self.generate_feature(
            f"""
Create Flask API endpoint for DynoAI_3:

{endpoint_spec}

Requirements:
- RESTful design
- Input validation with jsonschema
- Error handling with proper HTTP status codes
- Rate limiting support
- OpenAPI/Swagger documentation
- Unit tests with Flask test client
- Follow existing DynoAI_3 API patterns

Output location: api/routes/
"""
        )

    async def generate_frontend_component(self, component_spec: str) -> str:
        """
        Generate a React/TypeScript component for DynoAI_3 frontend.

        Args:
            component_spec: Specification of the component

        Returns:
            str: Summary of component generation
        """
        return await self.generate_feature(
            f"""
Create React/TypeScript component for DynoAI_3 frontend:

{component_spec}

Requirements:
- TypeScript with proper types
- React 18 functional components with hooks
- Responsive design
- Dark theme matching DynoAI_3 UI
- Error boundaries
- Loading states
- Unit tests with React Testing Library
- Storybook stories if complex

Output location: frontend/src/components/
"""
        )


async def interactive_menu():
    """Interactive menu for common DynoAI_3 development tasks."""
    integrator = DynoAI3DeepCodeIntegration()

    while True:
        print("\n" + "=" * 70)
        print("🎯 DynoAI_3 Feature Generator - Interactive Menu")
        print("=" * 70)
        print("\nWhat would you like to generate?")
        print()
        print("1. 🔧 New Analysis Module (Core Algorithm)")
        print("2. 🌐 API Endpoint")
        print("3. 🎨 Frontend Component")
        print("4. 📝 Tests for Existing Module")
        print("5. 📚 Documentation")
        print("6. 💡 Custom Feature (Free-form)")
        print("7. 🚪 Exit")
        print()

        choice = input("Enter your choice (1-7): ").strip()

        if choice == "1":
            print("\n📋 Analysis Module Generator")
            print("-" * 70)
            module_name = input("Module name (e.g., 'boost_analyzer'): ").strip()
            description = input("Brief description: ").strip()

            feature_spec = f"""
Create analysis module for DynoAI_3:

Module: dynoai/core/{module_name}.py

Description: {description}

Requirements:
- Deterministic analysis algorithm
- Input: pandas DataFrame with dyno data
- Output: Analysis results as dict or DataFrame
- Type hints for all functions
- Comprehensive docstrings
- Unit tests
- Example usage in docstring
"""
            await integrator.generate_feature(feature_spec)

        elif choice == "2":
            print("\n🌐 API Endpoint Generator")
            print("-" * 70)
            endpoint = input("Endpoint path (e.g., '/api/analyze-boost'): ").strip()
            method = input("HTTP method (GET/POST/PUT/DELETE): ").strip().upper()
            description = input("What does this endpoint do?: ").strip()

            feature_spec = f"""
Create API endpoint: {method} {endpoint}

Purpose: {description}

Include:
- Request/response schemas
- Input validation
- Error handling
- Rate limiting
- Unit tests
"""
            await integrator.generate_api_endpoint(feature_spec)

        elif choice == "3":
            print("\n🎨 Frontend Component Generator")
            print("-" * 70)
            component_name = input("Component name (e.g., 'BoostGauge'): ").strip()
            description = input("What does this component do?: ").strip()

            feature_spec = f"""
Component: {component_name}

Purpose: {description}

Requirements:
- TypeScript with proper types
- Responsive design
- Dark theme
- Loading/error states
"""
            await integrator.generate_frontend_component(feature_spec)

        elif choice == "4":
            print("\n📝 Test Generator")
            print("-" * 70)
            module_path = input(
                "Module path (e.g., 'dynoai/core/ve_math.py'): "
            ).strip()
            await integrator.generate_tests(module_path)

        elif choice == "5":
            print("\n📚 Documentation Generator")
            print("-" * 70)
            topic = input("Documentation topic: ").strip()
            await integrator.generate_documentation(topic)

        elif choice == "6":
            print("\n💡 Custom Feature Generator")
            print("-" * 70)
            print("Describe your feature in detail (press Enter twice when done):")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)

            feature_spec = "\n".join(lines[:-1])  # Remove last empty line
            await integrator.generate_feature(feature_spec)

        elif choice == "7":
            print("\n👋 Goodbye!")
            break

        else:
            print("\n❌ Invalid choice. Please enter 1-7.")

        input("\nPress Enter to continue...")


async def example_usage():
    """Example usage demonstrating various features."""
    integrator = DynoAI3DeepCodeIntegration()

    print("🎯 Running Example Feature Generation")
    print()

    # Example 1: Generate a new analysis module
    await integrator.generate_feature(
        """
Create a boost pressure analysis module for DynoAI_3:

Module: dynoai/core/boost_analyzer.py

Features:
- Analyze boost pressure data from dyno logs
- Calculate boost-by-RPM curves
- Detect boost leaks or wastegate issues
- Generate boost target tables
- Compare actual vs target boost
- Export results to CSV and plots

Input: CSV with columns: time, rpm, map, boost_psi, throttle_pos
Output: Boost analysis report with recommendations

Include:
- Type hints
- Comprehensive docstrings
- Unit tests
- Example usage
"""
    )


async def main():
    """Main entry point."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "DynoAI_3 <-> DeepCode Integration" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    # Check if DeepCode is accessible
    try:
        from workflows.agent_orchestration_engine import (
            execute_chat_based_planning_pipeline,
        )

        print("✅ DeepCode integration verified")
    except ImportError:
        print("❌ DeepCode not found. Please check the path.")
        return

    print()
    print("Choose mode:")
    print("1. Interactive Menu (Recommended)")
    print("2. Run Example Generation")
    print("3. Exit")
    print()

    choice = input("Enter choice (1-3): ").strip()

    if choice == "1":
        await interactive_menu()
    elif choice == "2":
        await example_usage()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
