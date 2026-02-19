"""
This script executes the main self-test routine from selftest.py.
It serves as a stable entry point for running the project's validation.
"""

import sys
from pathlib import Path

# Ensure the project root is in the path to allow importing selftest
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

try:
    # Import the main function from the robust selftest module
    from selftest import main as run_selftest
except ImportError:
    print("Error: Could not import 'run_selftest' from 'selftest'.", file=sys.stderr)
    print("Please ensure 'selftest.py' is in the same directory.", file=sys.stderr)
    sys.exit(1)

# Execute the self-test and exit with its status code
if __name__ == "__main__":
    sys.exit(run_selftest())
