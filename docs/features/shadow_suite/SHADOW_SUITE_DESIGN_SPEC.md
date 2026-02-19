# Shadow Suite Theme - Design Specification

## Color Token Reference

```python
# BACKGROUNDS
BG0 = "#0B0D10"  # Main app background - darkest
BG1 = "#0F1216"  # Card/panel background - dark
BG2 = "#131820"  # Hover/raised states - lighter

# STRUCTURE
BORDER = "#2A313B"  # All borders, dividers, lines

# TYPOGRAPHY
TEXT = "#D7DCE3"    # Primary text (off-white)
MUTED = "#9AA5B1"   # Secondary/muted text

# ACCENT (use sparingly)
ACCENT = "#8FA3B8"  # Steel blue - primary accent

# CONDITIONAL STATES (semantic use only)
OK = "#6FAF8A"      # Active/running/armed states
WARN = "#C7A86A"    # Warnings, AFR lean context
DANGER = "#C86B6B"  # Abort, destructive actions
```

## Before & After Comparison

### Old Theme Issues
❌ Too many colors competing for attention
❌ Heavy gradients and glows
❌ Buttons always green/yellow regardless of state
❌ Inconsistent spacing
❌ Large border radius (8px) - too soft
❌ Section headers too bright
❌ Mixed color definitions across files

### Shadow Suite Solutions
✅ Monochrome base + ONE accent color
✅ Flat surfaces, no gradients/glow
✅ Neutral buttons, state colors only when active
✅ Consistent 6/12/18/24px spacing rhythm
✅ Minimal 3px radius - precise feel
✅ Muted, ALL CAPS section headers
✅ Single source of truth in theme.py

## Component Style Guide

### Buttons

```python
# DEFAULT - Neutral, bordered
QPushButton:
  background: transparent
  color: TEXT
  border: 1px solid BORDER
  
# PRIMARY - ACCENT border (use sparingly)
QPushButton[variant="primary"]:
  background: transparent
  color: ACCENT
  border: 1px solid ACCENT
  
# STATE - OK color (only when active/running)
QPushButton[variant="state"]:
  background: transparent
  color: OK
  border: 1px solid OK
  
# DANGER - DANGER border (destructive only)
QPushButton[variant="danger"]:
  background: transparent
  color: DANGER
  border: 1px solid DANGER
```

### Typography Hierarchy

```python
# Headers - whisper, don't compete with data
QLabel[class="section"]:
  font-size: 10pt
  font-weight: 600
  color: MUTED
  text-transform: uppercase
  letter-spacing: 0.08em

# Values - speak, stand out
QLabel[class="value"]:
  font-size: 14pt
  font-weight: 600
  color: TEXT
  font-family: monospace

# Muted - de-emphasized
QLabel[class="muted"]:
  color: MUTED
```

### Panels & Cards

```python
QFrame[class="card"]:
  background-color: BG1
  border: 1px solid BORDER
  border-radius: 3px

QFrame[class="panel"]:
  background-color: BG1
  border: 1px solid BORDER
  border-radius: 3px
```

### Navigation

```python
# Sidebar
QWidget[class="sidebar"]:
  background-color: BG1
  border-right: 1px solid BORDER

# Nav items - subtle
QPushButton[class="nav-item"]:
  background: transparent
  color: MUTED
  border: none
  
QPushButton[class="nav-item"]:hover:
  background: BG2
  color: TEXT
  
QPushButton[class="nav-item"][active="true"]:
  background: BG2
  color: ACCENT
  border-left: 2px solid ACCENT
```

## Usage Examples

### Creating a Primary Action Button
```python
from gui.components.button import Button, ButtonVariant

# Neutral by default
btn = Button("Analyze", variant=ButtonVariant.DEFAULT)

# Primary action (ACCENT border)
btn = Button("Start Analysis", variant=ButtonVariant.PRIMARY)

# Active/running state (OK color)
btn.setProperty("variant", "state")
btn.style().polish(btn)
```

### Creating a Section Header
```python
header = QLabel("CONFIGURATION")
header.setProperty("class", "section")
```

### Creating a Value Display
```python
value = QLabel("145.3 HP")
value.setProperty("class", "value")
```

### Creating a Panel
```python
panel = QFrame()
panel.setProperty("class", "panel")
```

## Spacing System

```
XS:  6px  - tight spacing, inline elements
SM: 12px  - standard spacing, related items
MD: 18px  - medium spacing, section dividers
LG: 24px  - large spacing, major sections
```

## Typography Scale

```
Small:   10pt - Hints, captions, metadata
Base:    12pt - Body text, labels
Large:   14pt - Emphasized text, values
H2:      16pt - Sub-headers
H1:      20pt - Page titles
```

## Border & Radius

```
Border Width: 1px (consistent everywhere)
Border Radius: 3px (minimal, mechanical)
```

## Do's and Don'ts

### DO ✅
- Use MUTED for section headers
- Use TEXT for primary content
- Use ACCENT for focus states
- Use OK only when something is active/running
- Use DANGER only for destructive actions
- Keep borders 1px
- Keep radius 3px max
- Use flat surfaces

### DON'T ❌
- Don't use gradients
- Don't use drop shadows
- Don't use glow effects
- Don't make buttons green by default
- Don't use rainbow colors
- Don't use large border radius (>3px)
- Don't mix spacing units
- Don't hardcode colors inline

## Integration Checklist

When creating new components:

1. ☐ Import from `gui.styles.theme` if needed
2. ☐ Use property selectors (`setProperty("class", "...")`)
3. ☐ Reference design tokens, not hardcoded colors
4. ☐ Follow spacing rhythm (6/12/18/24)
5. ☐ Use semantic state colors appropriately
6. ☐ Test hover/focus/pressed states
7. ☐ Verify contrast ratios
8. ☐ Check on both light and dark monitors

## Accessibility Notes

- **Contrast Ratio:** TEXT on BG0 = 14.5:1 (AAA)
- **Muted Contrast:** MUTED on BG0 = 7.2:1 (AA)
- **Accent Contrast:** ACCENT on BG0 = 8.1:1 (AA)
- **State Colors:** All meet WCAG AA standards

## Engineering Philosophy

> "This is engineering software, not street racing. The UI should feel **compiled**, mechanically aligned, with a subsystem-label vibe. Labels whisper; numbers speak. No neon, no glow, just quiet precision."

The Shadow Suite theme embodies:
- **Industrial precision** - Clean lines, exact spacing
- **Minimal distraction** - Muted chrome, data stands out
- **Functional clarity** - Every color has semantic meaning
- **Engineering confidence** - Compiled, not flashy

---

**Reference Implementation:** `gui/styles/theme.py`  
**Last Updated:** December 31, 2025

