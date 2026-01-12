# PG27AQDM Low-Strain Themes

This workspace-local extension registers the two ergonomic WOLED-friendly themes so that they appear in VS Code's **Preferences → Color Theme** picker.

## Installation

1. Open the Extensions view.
2. Click the ••• menu → **Install from VSIX...**.
3. Run `pnpm dlx vsce package` (or `npx vsce package`) inside `extensions/pg27aqdm-low-strain` to create a `.vsix` file, then select it.
4. Reload the window. The Night & Day themes will now show up in the picker.

Because this is a workspace-specific extension, you can repackage and install it whenever you clone the repo onto a new machine.

## Palette source of truth

These themes are built from the master palette at `config/themes/pg27aqdm-palette.json`. Update that file first, then mirror changes here to keep colors consistent across tools (VS Code/Cursor, terminal, browser userCSS, etc.).