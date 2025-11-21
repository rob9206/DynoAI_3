# Security Triage (Initial Pass)

Categories observed (from earlier Snyk scan context):

1. Cookie / session security
   - Missing `Secure`, `HttpOnly`, `SameSite` on any future session cookies.
   - Action: When adding auth/session, configure Flask session cookie: `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, ensure HTTPS sets `SESSION_COOKIE_SECURE = True`.

2. Path traversal potential
   - File download/upload endpoints use `secure_filename` and controlled directories.
   - Action: Enforce whitelist of subdirectories, never allow `..` segments, re-validate resolved path: `resolved.is_relative_to(base)` (Python 3.11+) or manual check.

3. CSV formula injection
   - Any generated CSV that may be opened in Excel should escape leading characters `= + - @`.
   - Action: Introduce safe cell writer utility: prefix with `'` or space when a value starts with one of those characters.

4. Debug mode exposure
   - `DYNOAI_DEBUG` controls Flask debug; default should be `false` in deployments.
   - Action: Set `.env.example` to `DYNOAI_DEBUG=false` for production guidance.

5. External API key handling
   - xAI key read at call time; good for rotation. Ensure logs never print key.
   - Action: Redact headers in error paths; avoid echoing full response if it might contain secrets.

6. Rate limiting / abuse prevention
   - `/api/xai/chat` could be spammed.
   - Action: Add simple in-memory token bucket (per IP) or integrate with reverse proxy limits.

7. Manifest / VE operations integrity
   - Already uses SHA-256 hashing and rollback checks; good.
   - Action: Consider signing manifests (future) if external distribution is required.

## Immediate Remediation Plan

| Item | Priority | Change |
|------|----------|--------|
| Path validation | High | Add resolved path check in download route |
| CSV formula escaping | High | Add helper for CSV writes (VE deltas, coverage) |
| Debug default | Medium | Set example to `false`; doc note |
| Rate limiting | Medium | Implement lightweight per-IP limiter |
| Cookie flags | Low (no auth yet) | Add config placeholders now |
| Redaction | Low | Ensure exceptions never dump headers/key |

## Next Steps
1. Implement path normalization guard.
2. Introduce `safe_csv_cell(value: str) -> str` and use where CSV is written.
3. Flip `.env.example` debug to false.
4. Add simple rate limiter decorator.
5. Pre-configure secure cookie settings (harmless now, ready later).
6. Add tests for CSV escaping and path traversal prevention.
