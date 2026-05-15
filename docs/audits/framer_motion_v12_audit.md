# Framer Motion v12 Audit

**Audit date:** 2026-05-07  
**Installed version:** `framer-motion@^12.6.2`  
**Scope:** `frontend/src/**` callsites importing Framer Motion

---

## Summary

DynoAI's frontend is in good shape for Framer Motion v12. The codebase uses core `motion` and `AnimatePresence` APIs in supported ways, avoids known removed patterns like `exitBeforeEnter`, and already applies `mode="wait"` in transition-heavy flows.

Audit totals:

- 13 files import from `framer-motion`
- 32 `<motion.*>` elements
- 10 `<AnimatePresence>` blocks
- 0 deprecated API uses found

Result:

- **OK:** 6
- **Deprecated:** 0
- **Risky:** 0
- **Could-adopt:** 4

---

## Method (Context7)

Context7 library resolution selected:

- `/grx7/framer-motion`

Documentation pulled and compared against callsites:

- Core usage and `motion` component API
- `AnimatePresence` behavior and `mode="wait"` / `mode="popLayout"`
- `LazyMotion`, `MotionConfig`, `useInView`, `useScroll`, `useTransform`, `useSpring`

Context7 sources used:

- [Framer Motion llms docs](https://context7.com/grx7/framer-motion/llms.txt)
- [Framer Motion README](https://github.com/grx7/framer-motion/blob/main/packages/framer-motion/README.md)
- [AnimatePresence implementation details](https://github.com/grx7/framer-motion/blob/main/packages/framer-motion/src/components/AnimatePresence/index.tsx)

---

## Findings

### OK

- **Core import/API usage is valid in v12.**  
  Imports like `import { motion, AnimatePresence } from 'framer-motion'` are consistent across files such as `frontend/src/pages/JetDriveAutoTunePage.tsx`, `frontend/src/pages/AutoTuneDemo.tsx`, and `frontend/src/components/jetdrive/SetupWizard.tsx`.

- **`AnimatePresence mode="wait"` is already used correctly where sequencing matters.**  
  Seen in `frontend/src/components/jetdrive/SetupWizard.tsx` and `frontend/src/pages/AutoTuneDemo.tsx`, both with keyed children, matching the v12 wait-mode guidance.

- **No removed `exitBeforeEnter` usage.**  
  Repository-wide scan found zero occurrences.

- **Conditional exit animations are correctly wrapped.**  
  Patterns in `frontend/src/components/jetdrive/TelemetryStrip.tsx`, `frontend/src/components/reports/ReportGenerator.tsx`, and `frontend/src/components/jetdrive/TransientFuelPanel.tsx` follow current `AnimatePresence` usage.

- **List animation keys are present.**  
  Dynamic collections animated in `frontend/src/pages/OperatorTrainingPage.tsx` and `frontend/src/components/jetdrive/IngestionHealthPanel.tsx` include explicit keys.

- **Standard prop surface is used (`initial`, `animate`, `exit`, `transition`, `whileHover`, `whileTap`).**  
  No unsupported v12 prop patterns detected.

### Deprecated

- None found.

### Risky

- None found.

---

## Could-Adopt (v12-native optimizations)

- **Adopt `LazyMotion` for bundle trimming in heavy dashboards.**  
  `frontend/src/pages/JetDriveAutoTunePage.tsx` and `frontend/src/pages/OperatorTrainingPage.tsx` are large, animation-dense pages. `LazyMotion` + `m.*` can reduce initial animation payload.

- **Add `MotionConfig` at app shell for consistent defaults.**  
  A single `MotionConfig` around the app can standardize transition defaults and reduced-motion behavior without per-component duplication.

- **Implement reduced-motion policy explicitly.**  
  Current codebase has no `MotionConfig reducedMotion` and no `useReducedMotion` usage. Adding one global policy improves accessibility and avoids high-frequency motion on system-reduced settings.

- **Use `mode="popLayout"` + `layout` in expanding/collapsing UI clusters if layout jump appears.**  
  Candidates: `frontend/src/components/jetdrive/IngestionHealthPanel.tsx` and `frontend/src/components/jetdrive/TelemetryStrip.tsx`.

---

## High-Use Files (for future refactors)

- `frontend/src/pages/JetDriveAutoTunePage.tsx` (high traffic, multiple motion blocks)
- `frontend/src/components/jetdrive/AudioCapturePanel.tsx` (alert and recording micro-animations)
- `frontend/src/pages/AutoTuneDemo.tsx` (mode-switched motion sections)
- `frontend/src/components/jetdrive/DynoConfigPanel.tsx` (stepwise entrance motion)

These are the best targets if you want to standardize transition tokens or introduce `LazyMotion`.

---

## Recommendation

**Ship as-is for Framer Motion v12.** No migration work is required.

If you want a follow-up optimization pass, do this in order:

1. Add app-level `MotionConfig` with reduced-motion policy.
2. Introduce `LazyMotion` on the two largest animated pages.
3. Optionally tune collapsing panels with `popLayout` where visual jump is noticeable.

