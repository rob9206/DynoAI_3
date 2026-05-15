# Tailwind CSS v4 Configuration Audit

**Date:** 2026-05-07  
**Auditor:** Context7-assisted analysis (`/tailwindlabs/tailwindcss.com`, benchmark 83.97, High reputation)  
**Scope:** `frontend/tailwind.config.js`, `frontend/src/main.css`, `frontend/src/index.css`, `frontend/src/styles/theme.css`, `frontend/vite.config.ts`, `frontend/src/main.tsx`

---

## Summary

The DynoAI frontend runs **Tailwind CSS v4.1.11** and has partially adopted the v4 CSS-first model. The real entry point is `frontend/src/main.css`, which correctly uses `@import 'tailwindcss'`, `@custom-variant dark`, and `@config` to load the v3-style JS config as a compatibility bridge. However, the setup has four concrete problems:

1. **Unresolved spacing chain** -- `tailwind.config.js` replaces the entire spacing scale with `var(--size-*)` references. Those CSS variables are defined only inside `#spark-app { ... }` in `theme.css`, but DynoAI's root element is `id="root"`, not `id="spark-app"`. Every spacing utility generated from the JS config produces an unresolved `var()`, which the browser silently ignores.

2. **Dead Radix color tokens** -- The JS config extends Tailwind with 60+ numbered tokens (`neutral-1..12`, `accent-1..12`, etc.) that reference the same `#spark-app`-scoped CSS variables. Those variables never resolve; the Tailwind classes for them exist in the generated stylesheet but produce no visual output.

3. **Competing dark-theme palettes** -- `index.css` and `main.css` each define a `.dark { ... }` block with completely different color values (zinc/orange vs. PG27AQDM low-strain). The cascade silently discards one palette.

4. **Redundant Tailwind entry points** -- `main.css`, `theme.css`, and `index.css` each contain `@import 'tailwindcss'`. All three are also imported directly in `main.tsx`, causing triple-entry Tailwind imports. This bloats the generated CSS and makes import-order reasoning fragile.

No production-visible styling breakage from items 1 and 2 exists today because no component currently uses the affected Tailwind class names (`bg-neutral-1`, `p-4` from the custom scale, etc.). Items 3 and 4 affect every page load.

---

## Method

Documentation sourced via **Context7** on 2026-05-07:

| Topic | Context7 query | Source URL returned |
|---|---|---|
| CSS-first `@theme`, migrating from `theme.extend` | "CSS-first configuration @theme token custom colors spacing scale migration from theme.extend v3 to v4 automatic content detection" | `https://context7.com/tailwindlabs/tailwindcss.com/llms.txt` |
| `@custom-variant dark`, dark mode variants | "@custom-variant dark mode selector attribute darkMode replacement @variant custom breakpoints --breakpoint-* media queries" | `https://github.com/tailwindlabs/tailwindcss.com/blob/main/src/docs/dark-mode.mdx` |
| `@config` compat directive, upgrade CLI | "@config directive compatibility v3 config file upgrade migration tool npx @tailwindcss/upgrade" | `https://context7.com/tailwindlabs/tailwindcss.com/llms.txt` |

All doc quotes below are verbatim from those sources.

---

## Findings

### OK -- Working correctly under v4

| Artifact | File:line | Why it is correct |
|---|---|---|
| `@import 'tailwindcss';` | `main.css:1` | Correct v4 CSS entry point |
| `@custom-variant dark (&:is(.dark *));` | `main.css:9` | Proper v4 selector-based dark mode declaration |
| `@config '../tailwind.config.js';` | `main.css:11` | v4 compat bridge; JS config is loaded |
| `@theme inline { --color-accent: var(--accent); ... }` | `main.css:111-146` | shadcn/ui tokens mapped to v4 `--color-*` namespace |
| `next-themes` with `attribute="class"` | `App.tsx:490` | Adds `.dark` to `<html>`, matching the `@custom-variant` |

**Context7 citation (what v4 "correct" looks like):**

> "Move theme configuration from tailwind.config.js to app.css using @theme with CSS custom properties."  
> Source: `https://context7.com/tailwindlabs/tailwindcss.com/llms.txt`

```css
/* AFTER (v4): app.css */
@import "tailwindcss";

@theme {
  --color-brand: #4F46E5;
  --font-display: "Satoshi", "sans-serif";
}
```

The `@theme inline { ... }` block in `main.css` follows this pattern for the shadcn/ui semantic tokens. Those tokens work correctly.

---

### DEAD -- Configured but produces no output

#### Finding D1: Spacing scale references unresolved CSS variables

**File:lines:** `frontend/tailwind.config.js:104-140` (spacing definition) and `frontend/src/styles/theme.css:133-168` (`--size-*` variable definitions inside `#spark-app { }`)

The JS config replaces the default Tailwind spacing scale (not `extend.spacing` -- the bare `spacing` key, which replaces the entire scale):

```js
// frontend/tailwind.config.js:104-140
spacing: {
  px: "var(--size-px)",
  0:  "var(--size-0)",
  0.5: "var(--size-0-5)",
  1:  "var(--size-1)",
  // ... through 96
},
```

Those variables are defined only inside:

```css
/* frontend/src/styles/theme.css:133-168 */
#spark-app {
  --size-scale: 1;
  --size-px:  1px;
  --size-0:   0px;
  --size-1:   calc(0.25rem * var(--size-scale));
  /* ... */
}
```

The DynoAI app root is `<div id="root">` (`frontend/index.html:15`), not `id="spark-app"`. The CSS scope never matches. Every Tailwind spacing utility generated from the JS config -- `p-4`, `m-2`, `w-8`, `gap-6`, etc. -- resolves to `padding: var(--size-4)` where `--size-4` is undefined, which CSS treats as an invalid value (no style applied).

**Why no visible breakage today:** no component currently uses the custom Tailwind spacing classes from the JS config scale. Components use `p-4` etc., but those work because Tailwind v4's own default `--spacing` system generates those classes independently of the JS config's `spacing` object.

**Risk:** Any developer who adds a spacing class expecting Tailwind v4 defaults but the JS config's custom scale is active may get inconsistent results. If the v3 compat layer fully takes over spacing, the fallback to v4 defaults stops working.

---

#### Finding D2: Radix-style numbered color tokens reference the same dead scope

**File:lines:** `frontend/tailwind.config.js:26-93` (color extension) and `frontend/src/styles/theme.css:179-246` (color var definitions inside `#spark-app { }`)

The JS config extends Tailwind with 60+ numbered color tokens:

```js
// frontend/tailwind.config.js:26-93 (excerpt)
extend: {
  colors: {
    neutral: {
      1:  "var(--color-neutral-1)",
      // ... through 12, a1-a12, contrast
    },
    accent: {
      1:  "var(--color-accent-1)",
      // ... through 12, contrast
    },
    "accent-secondary": { /* ... */ },
    fg:  { DEFAULT: "var(--color-fg)", secondary: "var(--color-fg-secondary)" },
    bg:  { DEFAULT: "var(--color-bg)", inset: "var(--color-bg-inset)", overlay: "var(--color-bg-overlay)" },
  },
}
```

Those CSS variables are defined only in the same `#spark-app { }` scope in `theme.css:179-246`. Since that scope never applies (root is `#root`), any component that uses `bg-neutral-1`, `text-accent-9`, `text-fg`, `bg-bg-inset`, etc. would render with no color applied.

**Grep result:** no component in `frontend/src/**/*.{tsx,ts,jsx,js}` currently uses these numbered tokens as Tailwind class names. The JS config creates the classes; nothing consumes them.

---

#### Finding D3: `darkMode` in JS config is overridden and never activates

**File:lines:** `frontend/tailwind.config.js:141` vs. `frontend/src/main.css:9`

```js
// frontend/tailwind.config.js:141
darkMode: ["selector", '[data-appearance="dark"]'],
```

This would make Tailwind generate `.dark:` utilities scoped to `[data-appearance="dark"]` on an ancestor. But `main.css:9` overrides the dark variant:

```css
/* frontend/src/main.css:9 */
@custom-variant dark (&:is(.dark *));
```

**Context7 citation (authoritative v4 behavior):**

> "To use class-based dark mode instead of the default prefers-color-scheme media query, override the dark variant with @custom-variant. The selector `(&:where(.dark, .dark *))` activates dark mode utilities whenever the `.dark` class is present on an ancestor element."  
> Source: `https://github.com/tailwindlabs/tailwindcss.com/blob/main/src/docs/dark-mode.mdx`

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));
```

Because CSS-first directives take precedence over `@config` JS config settings in v4, the `@custom-variant dark` in `main.css` wins. The JS config's `darkMode: ["selector", '[data-appearance="dark"]']` is never applied. The actual dark trigger is the `.dark` class added by `next-themes` (`App.tsx:490`: `attribute="class"`). The `data-appearance` attribute is never toggled anywhere in the codebase (confirmed by grep; zero matches).

---

### DRIFTED -- Live but inconsistent

#### Finding DR1: Two competing `.dark { ... }` palette blocks

**Files:lines:** `frontend/src/index.css:146-203` (zinc/orange palette) and `frontend/src/main.css:74-106` (PG27AQDM low-strain palette)

`main.css` imports `index.css` on line 4, then defines its own `.dark` block on line 74. Because `main.css`'s block appears later in the same file, it overwrites `index.css`'s definitions via CSS cascade. The PG27AQDM palette wins.

The zinc/orange palette in `index.css` is effectively dead for dark mode. It still applies in other blocks (`index.css:98-144` light `:root`) but main.css's `:root` (lines 36-67) overwrites those too.

**Risk:** A developer editing `index.css`'s dark theme believes they are changing the app's dark appearance. They are not.

---

#### Finding DR2: Redundant `@import 'tailwindcss'` in three CSS files

**Files:lines:**
- `frontend/src/main.css:1` -- primary entry
- `frontend/src/styles/theme.css:1` -- duplicated
- `frontend/src/index.css:1` -- duplicated

**Additionally**, `main.tsx` imports all three files directly:

```ts
// frontend/src/main.tsx:7-9
import "./main.css"
import "./styles/theme.css"
import "./index.css"
```

Even though `main.css` already imports `theme.css` and `index.css`, the direct `main.tsx` imports cause Vite to track all three files as independent Tailwind CSS entry points. Depending on the `@tailwindcss/vite` plugin version, this may generate multiple copies of the Tailwind base layer in the bundle or emit confusing HMR behavior when any of the three files changes.

**Context7 citation (v4 content detection):**

> "You know how you always had to configure that annoying `content` array in Tailwind CSS v3? In v4.0, we came up with a bunch of heuristics for detecting all of that stuff automatically so you don't have to configure it at all."  
> Source: `https://github.com/tailwindlabs/tailwindcss.com/blob/main/src/blog/tailwindcss-v4/index.mdx`

In v4, Tailwind scans for content automatically from a single CSS entry point. Multiple entry points are not the intended usage model and can confuse the scanner.

---

#### Finding DR3: `@theme inline` in `main.css` duplicates `@theme` in `index.css`

**Files:lines:** `frontend/src/main.css:111-175` (`@theme inline`) and `frontend/src/index.css:205-232` (`@theme`)

Both define the same token names (`--color-background`, `--color-foreground`, `--color-accent`, etc.). In v4, `@theme inline` emits values as inline CSS properties without generating separate custom properties; `@theme` (without `inline`) generates custom properties on `:root`. Both modes generate the same utility class names, so the duplication is redundant rather than broken -- but it makes token maintenance a two-file exercise and obscures which definition is authoritative.

---

### MISSING -- Configured but never used

| Token / Feature | Configured in | Used in components | Impact |
|---|---|---|---|
| `screens.coarse`, `screens.fine`, `screens.pwa` | `tailwind.config.js:21-25` | Zero occurrences in `frontend/src/**` | Dead config; classes generated but never needed |
| `neutral-1..12`, `accent-1..12`, `accent-secondary-1..12` | `tailwind.config.js:26-93` + `theme.css` | Zero occurrences as Tailwind class names | Dead config; CSS vars also unresolved (see D2) |
| `fg`, `fg-secondary`, `bg`, `bg-inset`, `bg-overlay` | `tailwind.config.js:84-93` + `theme.css` | Zero occurrences as Tailwind class names | Dead config |

---

## Recommended path

### Option A -- CSS-first migration (recommended)

Eliminates all four problems by removing the JS config and moving everything into the CSS entry point.

**Steps:**

1. **Delete** `frontend/tailwind.config.js`.

2. **Consolidate to a single CSS entry point** (`main.css`). Remove `@import './index.css'` and `@import './styles/theme.css'` from `main.css` -- fold the content that matters from each file directly into `main.css` or deduplicated sibling partials. Remove the duplicate imports from `main.tsx`.

3. **Move custom breakpoints** into `main.css`'s `@theme` block:
   ```css
   @theme {
     --breakpoint-coarse: (pointer: coarse);   /* @custom-variant, not --breakpoint-* */
     /* ... */
   }
   ```
   Actually for pointer media queries, use `@custom-variant` per the v4 docs:
   ```css
   @custom-variant coarse (@media (pointer: coarse));
   @custom-variant fine   (@media (pointer: fine));
   @custom-variant pwa    (@media (display-mode: standalone));
   ```
   **Context7 citation:**
   > "Create a custom variant for touch devices: `@custom-variant touch (@media (hover: none) and (pointer: coarse));`"  
   > Source: `https://context7.com/tailwindlabs/tailwindcss.com/llms.txt`

4. **Move `extend.colors`** into `@theme`:
   ```css
   @theme {
     --color-neutral-1:  var(--bronze-1);   /* now global, not #spark-app scoped */
     --color-neutral-2:  var(--bronze-2);
     /* ... */
   }
   ```
   Move the Radix color variable _definitions_ (`--bronze-*` etc.) out of `#spark-app` scope to `:root`.

5. **Replace the spacing scale** with v4's native `--spacing` approach or a v4 `@theme` spacing block:
   ```css
   @theme {
     --spacing: 0.25rem;   /* v4's single multiplier -- p-4 → 1rem */
   }
   ```
   Remove the per-step `var(--size-*)` pattern entirely. Move the `--size-scale` multiplier concept to a separate non-spacing mechanism if the scaling behavior is still needed.

6. **Remove the redundant `darkMode` key** from the now-deleted JS config. Keep `@custom-variant dark (&:is(.dark *));` as the sole dark-mode declaration.

7. **Reconcile the two `.dark { ... }` blocks** -- pick one palette (the PG27AQDM one in `main.css` is what users currently see) and delete the other.

**What `npx @tailwindcss/upgrade` automates:**

The official upgrade tool handles steps 1 and 4 automatically (JS config → CSS) and some of step 2 (import consolidation). Run it on a new branch first:
```bash
npx @tailwindcss/upgrade
```
**Context7 citation:**
> "Run the upgrade tool to automatically migrate tailwind.config.js to CSS, update dependencies, and adjust template syntax. Requires Node.js 20+."  
> Source: `https://context7.com/tailwindlabs/tailwindcss.com/llms.txt`

Steps 3, 5, and 7 (custom variants, spacing rework, palette reconciliation) require manual review because they involve DynoAI-specific decisions.

---

### Option B -- Compat bridge (fastest, transitional)

Keep `@config '../tailwind.config.js'` in `main.css` but fix only the two root-cause issues: the `#spark-app` scope and the duplicate CSS files.

**Steps:**

1. **Move the `--size-*` and `--color-*` variable definitions** in `theme.css` from `#spark-app { }` to `:root { }`. This immediately unblocks the spacing and color chains.

2. **Remove the duplicate `@import 'tailwindcss'` lines** from `theme.css:1` and `index.css:1`. Keep only the one in `main.css:1`.

3. **Remove the direct `import "./styles/theme.css"` and `import "./index.css"` lines from `main.tsx`** -- `main.css` already imports them.

4. **Reconcile the two `.dark { ... }` blocks** -- delete `index.css:146-203` (the zinc/orange palette that is never seen).

5. **Add a comment** above the `@config` line explaining it is a transitional bridge pending full CSS-first migration.

This path leaves `tailwind.config.js` in place (including the dead `darkMode`, unused custom screens, and JS-config maintenance burden) but stops the unresolved-variable breakage and import disorder.

---

## Decision aids

| Concern | Option A | Option B |
|---|---|---|
| Time to fix the unresolved spacing chain | Medium (requires spacing rework) | Fast (change `#spark-app` to `:root`) |
| Eliminates JS config maintenance | Yes | No |
| Risk of regressions | Medium (full migration) | Low (targeted fixes) |
| What `npx @tailwindcss/upgrade` covers | ~70% of the work | Not applicable |
| Leaves dead `darkMode` / `screens` config | No | Yes (still in JS config) |
| Suitable path if F1 autotune work is imminent | No -- defer until autotune stable | Yes -- minimal risk |
| Long-term cleanliness | Clean v4 CSS-first | Technical debt remains |

**Immediate recommendation:** apply Option B steps 1-4 now (30-minute fix, no regression risk) to stop the unresolved-variable problem. Schedule Option A as a follow-up task once the F1 autotune preview pipeline is complete and the frontend is in a lower-churn state.
