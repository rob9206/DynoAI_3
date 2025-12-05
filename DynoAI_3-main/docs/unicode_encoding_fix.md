# Unicode Encoding Fix for Windows Console

## Issue

The application was experiencing a `UnicodeEncodeError` when running on Windows:

```
'charmap' codec can't encode character '\U0001f4e4' in position 0: character maps to <undefined>
```

This error occurred because the code was using emoji characters (🚀, 📁, 🐍, ✅, ❌, etc.) in print statements, but the Windows console uses the `cp1252` (Windows-1252) encoding by default, which doesn't support these Unicode emoji characters.

## Root Cause

The Windows console encoding (`cp1252`) doesn't support emoji characters, which are part of the Unicode standard but outside the basic multilingual plane. When Python tries to print these characters to the console, it fails with a `UnicodeEncodeError`.

## Solution

Replaced all emoji characters with ASCII-safe alternatives that work across all console encodings:

| Emoji | ASCII Replacement | Meaning |
|-------|------------------|---------|
| 🚀 | `[*]` | Starting/Running |
| 📁 📦 | `[>]` | Action/Processing |
| ✅ | `[+]` | Success |
| ❌ | `[-]` | Error/Failure |
| 🧪 | `[*]` | Testing |
| ⏳ | `[*]` | Waiting |
| 🌐 📡 | `[*]` | Network/Server |
| 🛑 | `[*]` | Stopping |
| 👋 | `[*]` | Goodbye |

## Files Modified

### Python Files
- `api/app.py` - Flask API server startup messages and logging
- `test_api.py` - API test script output

### PowerShell Scripts
- `start-web.ps1` - Web application startup script
- `test-api.ps1` - API integration test script
- `test-api-only.ps1` - API-only test script

### Shell Scripts
- `start-dev.sh` - Development server startup script

## Testing

All modified files were tested to ensure:
1. ✅ No encoding errors on Windows console (cp1252)
2. ✅ No linter errors introduced
3. ✅ No security issues (Snyk Code scan passed)
4. ✅ Output remains clear and readable

## Verification

To verify the console encoding on your system:

```python
import sys
print(sys.stdout.encoding)
```

On Windows, this typically returns `cp1252`, which doesn't support emoji characters.

## Best Practices

When writing Python code that outputs to the console:

1. **Use ASCII-safe characters** for console output that needs to work across all platforms
2. **Test on Windows** if your application will run on Windows systems
3. **Consider the target encoding** - not all terminals support full Unicode
4. **Use emojis only in**:
   - Web interfaces (HTML/CSS)
   - Documentation (Markdown)
   - GUI applications
   - Files with explicit UTF-8 encoding

## Related Issues

This fix addresses the issue documented in `docs/test_failures_baseline.md - Issue #2: Use ASCII for Windows compatibility`.

## Future Considerations

If emoji support is desired in the future, consider:

1. **Environment detection**: Check if the console supports UTF-8 before using emojis
2. **Configuration option**: Allow users to enable/disable emoji output
3. **UTF-8 mode**: Use Python's UTF-8 mode (`PYTHONIOENCODING=utf-8`) but this requires user configuration
4. **Rich library**: Use libraries like `rich` that handle encoding gracefully

## References

- [Python Unicode HOWTO](https://docs.python.org/3/howto/unicode.html)
- [Windows Console and Unicode](https://docs.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences)
- [PEP 540 - Add a new UTF-8 Mode](https://www.python.org/dev/peps/pep-0540/)

