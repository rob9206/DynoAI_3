## Description

<!-- Provide a clear and concise description of your changes -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Infrastructure/CI change
- [ ] Refactoring (no functional changes)

## DynoAI Safety Checklist

**CRITICAL:** Verify that your changes do NOT modify any tuning math or kernel behavior:

- [ ] I have NOT changed VE correction math
- [ ] I have NOT changed AFR error calculations
- [ ] I have NOT changed torque/HP weighting formulas
- [ ] I have NOT changed kernel behavior (k1, k2, k3)
- [ ] I have NOT changed VE grid shape or clamp rules
- [ ] I have NOT changed `VEApply`/`VERollback` numerical behavior
- [ ] OR: This PR explicitly modifies tuning math and has been reviewed by the Math Guardian Agent

## Testing

- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] Self-tests pass (`python tool/selftest_runner.py`)
- [ ] New tests added for new functionality (if applicable)
- [ ] Code coverage maintained or improved
- [ ] Tested on both Linux and Windows (if platform-specific changes)

## Code Quality

- [ ] Code follows project style guidelines
- [ ] `flake8` passes with no critical errors
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Type hints added where appropriate
- [ ] Documentation updated (docstrings, README, etc.)

## Additional Context

<!-- Add any other context about the PR here -->
<!-- Link related issues: Fixes #123, Resolves #456 -->
