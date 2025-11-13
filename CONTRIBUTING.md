# Contributing to DynoAI_3

Thank you for your interest in contributing to DynoAI_3! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Code Review Process](#code-review-process)
- [Style Guidelines](#style-guidelines)
- [Math-Critical Code](#math-critical-code)

## Code of Conduct

By participating in this project, you are expected to uphold our code of conduct:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members
- Accept constructive criticism gracefully

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/DynoAI_3.git
   cd DynoAI_3
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/rob9206/DynoAI_3.git
   ```

## Development Setup

1. **Install Python 3.9 or higher**
   ```bash
   python --version  # Should be 3.9+
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```

4. **Install pre-commit hooks** (if configured)
   ```bash
   pre-commit install
   ```

## Making Changes

1. **Create a new branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following the style guidelines below

3. **Write tests** for your changes (see Testing section)

4. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git add .
   git commit -m "Add feature: brief description of what you did"
   ```

   Good commit message examples:
   - `Add validation for input parameters in core/math_utils.py`
   - `Fix edge case in experiments/protos/algorithm.py`
   - `Update documentation for API endpoints`

## Testing

All code changes must include appropriate tests. We use pytest for testing.

### Running Tests

```bash
# Run all tests
pytest

# Run specific test types
pytest tests/unit          # Unit tests
pytest tests/integration   # Integration tests
pytest tests/kernel        # Kernel tests

# Run with coverage
pytest --cov=. --cov-report=html
```

### Test Structure

- **Unit tests** (`tests/unit/`): Test individual functions and classes
- **Integration tests** (`tests/integration/`): Test component interactions
- **Kernel tests** (`tests/kernel/`): Test core system functionality

### Writing Tests

- Write tests for all new functionality
- Ensure tests are deterministic and reproducible
- Use descriptive test names: `test_function_name_when_condition_then_expected_result`
- Include edge cases and error conditions

## Submitting Changes

1. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request** on GitHub:
   - Use the PR template provided
   - Fill in all relevant sections
   - Link related issues
   - Provide a clear description of changes

3. **Ensure CI passes**:
   - All tests must pass
   - Code must pass linting checks
   - CodeQL security analysis must pass
   - No new security vulnerabilities

## Code Review Process

1. **Automated checks** run on all PRs:
   - Python CI (tests, linting)
   - CodeQL security analysis
   - Dependency review

2. **Human review**:
   - At least one maintainer must approve
   - Address all review comments
   - Math-critical code requires extra scrutiny

3. **Merge requirements**:
   - All CI checks must pass
   - All conversations must be resolved
   - Branch must be up-to-date with main

## Style Guidelines

### Python Code Style

We follow PEP 8 with some modifications:

- **Line length**: Maximum 127 characters
- **Imports**: Use `isort` for import ordering
- **Formatting**: Use `black` for code formatting
- **Type hints**: Use type hints for function signatures
- **Docstrings**: Use Google-style docstrings

### Code Quality

```bash
# Format code with black
black .

# Sort imports with isort
isort .

# Check with flake8
flake8 .

# Type checking with mypy (if configured)
mypy .
```

### Documentation

- Update documentation for any API changes
- Add docstrings to all public functions and classes
- Include examples in docstrings where helpful
- Update README.md if adding major features

### Example Docstring

```python
def calculate_something(x: float, y: float) -> float:
    """Calculate something based on x and y.
    
    Args:
        x: The first parameter as a float.
        y: The second parameter as a float.
        
    Returns:
        The calculated result as a float.
        
    Raises:
        ValueError: If x or y is negative.
        
    Example:
        >>> calculate_something(2.0, 3.0)
        6.0
    """
    if x < 0 or y < 0:
        raise ValueError("Parameters must be non-negative")
    return x * y
```

## Math-Critical Code

Files in `core/` and `experiments/protos/` contain math-critical algorithms. Extra care is required:

### Guidelines for Math-Critical Changes

1. **Thorough Testing**:
   - Include extensive unit tests with known results
   - Test edge cases and boundary conditions
   - Include numerical stability tests
   - Document the mathematical basis for tests

2. **Documentation**:
   - Explain the mathematical approach
   - Cite academic papers or references if applicable
   - Document assumptions and limitations
   - Include numerical examples

3. **Code Review**:
   - Math-critical PRs require detailed review
   - Provide mathematical justification for changes
   - Be prepared to explain your approach

4. **Validation**:
   - Validate against known results or benchmarks
   - Compare with reference implementations if available
   - Document validation methodology

### Example Math-Critical Test

```python
def test_matrix_multiply_known_result():
    """Test matrix multiplication against known mathematical result."""
    # Test case from "Linear Algebra Done Right" by Axler, Example 3.2
    A = np.array([[1, 2], [3, 4]])
    B = np.array([[5, 6], [7, 8]])
    expected = np.array([[19, 22], [43, 50]])
    
    result = matrix_multiply(A, B)
    
    np.testing.assert_array_almost_equal(result, expected)
```

## Questions?

If you have questions about contributing:

1. Check existing [issues](https://github.com/rob9206/DynoAI_3/issues)
2. Start a [discussion](https://github.com/rob9206/DynoAI_3/discussions)
3. Reach out to the maintainers

## License

By contributing to DynoAI_3, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to DynoAI_3! 🚀
