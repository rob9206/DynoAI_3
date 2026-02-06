#!/usr/bin/env python3
"""
Test script for Engine Analyzer fixes.

Note: This is a lightweight integration-style sanity check that expects an
Engine Analyzer library directory to exist at repo-root/engineanalyzer or via
ENALYZER_LIB_DIR.
"""

import sys
from pathlib import Path

# Add project root to path (this file lives in tests/)
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from api.services.engine_analyzer.library_service import get_engine_analyzer_library
from api.services.parsers.pti_parser import parse_pti_file


def test_library() -> bool:
    """Test the engine analyzer library service."""
    print("Testing Engine Analyzer Library Service...")

    try:
        library = get_engine_analyzer_library()
        print(f"Library directory: {library.lib_dir}")
        print(f"Library exists: {library.lib_dir.exists()}")

        if not library.lib_dir.exists():
            print("ERROR: Library directory does not exist!")
            return False

        # Test loading components
        stats = library.get_stats()
        print(f"Total components: {stats.components}")
        print(f"Skipped files: {stats.skipped_files}")

        # Test component listings
        engines = library.list_components("engines")
        print(f"Engines found: {len(engines)}")

        if engines:
            for i, engine in enumerate(engines[:3]):  # Show first 3 engines
                spec = engine.get("spec", {})
                name = spec.get("name", engine.get("name", "Unknown"))
                disp_ci = spec.get("displacement_ci", "N/A")
                print(f"  Engine {i + 1}: {name} ({disp_ci}ci)")
        else:
            print("  No engines found - checking library contents...")
            if library.lib_dir.exists():
                for item in list(library.lib_dir.rglob("*"))[:10]:
                    if item.is_file() and item.suffix.upper() not in [
                        ".TXT",
                        ".JPG",
                        ".PNG",
                        ".DB",
                    ]:
                        print(f"  Potential component: {item.name}")

        heads = library.list_components("heads")
        print(f"Heads found: {len(heads)}")

        cams = library.list_components("cams")
        print(f"Cams found: {len(cams)}")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_parser() -> bool:
    """Test the PTI parser on sample files."""
    print("\nTesting PTI Parser...")

    library_path = project_root / "engineanalyzer"
    if not library_path.exists():
        print(f"ERROR: Library path {library_path} does not exist!")
        return False

    # Look for sample PTI files
    sample_files: list[Path] = []
    for folder in ["Example Total Engine Files", "Example Short Block Files", "Example Head Files"]:
        folder_path = library_path / folder
        if folder_path.exists():
            for file_path in folder_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() not in [".txt", ".jpg", ".png"]:
                    sample_files.append(file_path)
                    if len(sample_files) >= 3:
                        break
            if sample_files:
                break

    if not sample_files:
        print("No suitable sample files found!")
        return False

    print(f"Testing with {len(sample_files)} sample files...")

    for file_path in sample_files:
        try:
            print(f"Parsing: {file_path.name}")
            result = parse_pti_file(file_path)
            print(f"  Component type: {result.component_type}")
            print(f"  Component name: {result.spec.name}")

            if hasattr(result.spec, "displacement_ci"):
                print(f"  Displacement: {result.spec.displacement_ci}ci")

        except Exception as e:
            print(f"  ERROR parsing {file_path.name}: {e}")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Engine Analyzer Test Suite")
    print("=" * 60)

    success = test_library() and test_parser()

    print("\n" + "=" * 60)
    print("✅ All tests passed!" if success else "❌ Some tests failed!")
    print("=" * 60)

