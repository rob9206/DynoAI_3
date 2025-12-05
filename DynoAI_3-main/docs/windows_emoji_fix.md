# Windows Emoji Encoding Fix

## Issue
Windows console uses `cp1252` encoding by default, which doesn't support emoji characters. This caused `UnicodeEncodeError` when running Python scripts with emoji in print statements.

## Error Example
```
'charmap' codec can't encode character '\U0001f4e4' in position 0: character maps to <undefined>
```

## Solution
Replaced all emoji characters in Python files with ASCII alternatives:

- 🚀 → `[*]`
- 📁, 📊 → `[*]`
- 📤 → `[>]`
- ✓, ✅ → `[OK]`
- ❌ → `[ERROR]` or `[FAIL]`
- ⚠️ → `[WARN]`
- 🏷️ → `[*]`
- 💡 → `[INFO]`

## Files Fixed

### Critical Files (Production)
- `api/app.py` - Main API server startup messages and file upload messages
- `ve_operations.py` - VE table operation success messages
- `experiments/kernel_metrics.py` - Metrics reporting
- `experiments/baseline_generator.py` - Baseline generation messages
- `tools/todoist_helper.py` - Todoist integration messages

### Test Files
- `acceptance_test.py` - Acceptance test validation messages

## Verification
The fix was verified by testing print statements with ASCII characters on Windows console (cp1252 encoding), which succeeded without errors.

## Notes
- Test files still contain emojis but these are less critical as they're not typically run in production
- Future code should avoid using emoji characters in print statements to maintain Windows compatibility
- Consider using logging with proper encoding configuration for better cross-platform support

