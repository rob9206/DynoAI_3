## PG27AQDM Low-Strain Master Palette

This directory contains the single source of truth for the low-strain, deuteranopia-friendly color palette used across the workspace.

- Hardware/ambient assumptions: ASUS PG27AQDM WOLED, ~40 brightness, 6500K, mixed daylight/warm lamp.
- Goals: mid-saturation, sRGB-safe; lifted dark backgrounds; off-white text; avoid pure black/white; target ~7:1–10:1 contrast; do not rely on red vs green alone.

### Files
- `pg27aqdm-palette.json`: Master palette with `night` and `day` variants and commonly used derived tokens.

### Consumption
Map the palette into each app's format:
- VS Code/Cursor themes (`.vscode/themes/*.json` or `extensions/pg27aqdm-low-strain/themes/*.json`)
  - `editor.background` ← `bg`
  - `editor.foreground` ← `fgText`
  - `editorCursor.foreground` ← `accentPrimary`
  - `editor.lineHighlightBackground` ← `derived.lineHighlightBg`
  - `editor.selectionBackground` ← `derived.selectionBg`
  - Use `ok`/`warn`/`error`/`info` for diagnostics and VCS decorations
- Terminals, browsers, and other apps should follow the same mapping semantics.

### Updating the palette
1. Edit `pg27aqdm-palette.json` with small, explicit changes.
2. Propagate to themes/configs (VS Code/Cursor, terminal, userCSS) using the same keys.
3. Keep hues mid-saturation; prefer luminance + hue for semantic distinction.

### Notes
- The `night` and `day` variants differ mainly in backgrounds and small luminance tweaks to retain comfortable contrast across lighting conditions.
- Avoid introducing additional palettes; update this file and propagate.


