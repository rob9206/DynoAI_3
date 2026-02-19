/**
 * Small, dependency-free sanitizers for client-side safety.
 *
 * These helpers are intentionally conservative; they are used for:
 * - URL path segment encoding (to avoid path injection / traversal)
 * - Download filename sanitization (to avoid odd DOM/file behaviors)
 */

/**
 * Encode a value intended to be placed into a URL path segment.
 * (Do not use for full URLs.)
 */
export function encodePathSegment(value: string): string {
  return encodeURIComponent(String(value))
}

/**
 * Sanitize a user/server-provided filename for use as `a.download`.
 * - Removes path separators and control chars
 * - Replaces Windows-reserved characters with underscores
 * - Enforces a reasonable max length
 */
export function sanitizeDownloadName(name: string, fallback: string = "download"): string {
  const raw = String(name ?? "")
  const base = raw.split(/[/\\]/).pop() ?? ""

  // Strip control characters (incl. DEL) and trim.
  let clean = base.replace(/[\u0000-\u001F\u007F]/g, "").trim()

  // Replace Windows-reserved characters.
  clean = clean.replace(/[:*?"<>|]/g, "_")

  // Collapse whitespace.
  clean = clean.replace(/\s+/g, " ")

  if (!clean) clean = fallback

  // Prevent extremely long filenames (keep extension when possible).
  const MAX_LEN = 180
  if (clean.length > MAX_LEN) {
    const lastDot = clean.lastIndexOf(".")
    const hasExt = lastDot > 0 && clean.length - lastDot <= 12
    if (hasExt) {
      const ext = clean.slice(lastDot)
      const stemMax = Math.max(1, MAX_LEN - ext.length)
      clean = clean.slice(0, stemMax) + ext
    } else {
      clean = clean.slice(0, MAX_LEN)
    }
  }

  return clean
}


