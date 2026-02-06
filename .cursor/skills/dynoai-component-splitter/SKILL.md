---
name: dynoai-component-splitter
description: Provides a systematic workflow for decomposing large React components in the DynoAI frontend. Identifies extraction candidates, creates sub-components following project patterns (shadcn/ui, Radix, Tailwind). Use when the user asks to split, refactor, decompose, or break up a large React component, or when a component exceeds 300 lines.
---

# DynoAI Component Splitter

## When to Use

Apply this workflow when:
- A component exceeds ~300 lines
- A component has 3+ distinct visual sections
- A component manages unrelated pieces of state
- Props are being drilled 3+ levels deep
- The same JSX pattern appears twice in one file

Known large components to target:
- `frontend/src/components/jetdrive/TuningWizard.tsx` (~1031 lines)
- `frontend/src/pages/JetDriveAutoTunePage.tsx` (large)

## Extraction Workflow

### Step 1: Analyze the Component

Read the component and identify:

```
Analysis for [ComponentName]:
- Total lines: ___
- useState calls: ___ (list each)
- useEffect calls: ___
- useMemo/useCallback calls: ___
- Custom hook calls: ___
- Distinct visual sections: ___ (list each)
- Repeated JSX patterns: ___ (list each)
- Props received: ___
- Props drilled to children: ___
```

### Step 2: Identify Extraction Candidates

Score each candidate (higher = better extraction target):

| Signal | Score | Description |
|---|---|---|
| Independent state | +3 | Section has its own useState, no shared state |
| Repeated JSX | +3 | Same pattern appears 2+ times |
| Visual boundary | +2 | Clear section (card, panel, tab content) |
| 50+ lines of JSX | +2 | Large render block |
| Used in only one parent | +1 | Not blocking, but simpler extraction |
| Deeply shared state | -2 | Entangled with parent state (harder to extract) |
| Many callbacks from parent | -1 | Needs lots of props passed in |

Extract candidates scoring 3+. Start with the highest-scoring ones.

### Step 3: Choose Extraction Strategy

| Situation | Strategy | Example |
|---|---|---|
| Independent visual section | **Extract to component** | `<WizardStepHeader />` |
| Repeated JSX with variations | **Extract with props** | `<MetricCard label={} value={} />` |
| Complex state logic | **Extract to custom hook** | `useWizardNavigation()` |
| State + UI together | **Extract both** | `useStepValidation()` + `<StepValidator />` |
| Large switch/conditional | **Extract case components** | `<StepContent step={current} />` |

### Step 4: Create Sub-Components

Follow DynoAI frontend conventions:

**File location:**
```
# If parent is in components/<feature>/:
components/<feature>/<SubComponent>.tsx

# If parent is a page:
components/<feature>/<SubComponent>.tsx  (create feature dir if needed)
```

**Component template:**

```tsx
import { type ComponentProps } from "react";

interface <SubComponent>Props {
  // Only the props this component needs
}

export function <SubComponent>({ prop1, prop2 }: <SubComponent>Props) {
  return (
    <div className="...">
      {/* Extracted content */}
    </div>
  );
}
```

**Conventions:**
- Named exports for sub-components (not default)
- Default exports only for page-level components
- Props interface named `<ComponentName>Props`
- Use Tailwind classes (not CSS modules or styled-components)
- Import shadcn/ui from `@/components/ui/<component>`
- Use `cn()` from `@/lib/utils` for conditional classes

### Step 5: Extract Custom Hook (if needed)

When extracting state logic:

```typescript
// frontend/src/hooks/use<Feature><Concern>.ts

import { useState, useCallback, useMemo } from "react";

export function use<Feature><Concern>() {
  const [state, setState] = useState(initialValue);

  const derivedValue = useMemo(() => {
    // computation
  }, [state]);

  const action = useCallback(() => {
    setState(/* ... */);
  }, []);

  return {
    state,
    derivedValue,
    action,
  };
}
```

### Step 6: Refactor Parent

Replace extracted sections in the parent:

```tsx
// Before: 1000+ line component with inline sections
function TuningWizard() {
  // 50 lines of state
  // 100 lines of handlers
  return (
    <div>
      {/* 200 lines of header */}
      {/* 300 lines of step content */}
      {/* 200 lines of footer */}
    </div>
  );
}

// After: Composed from focused sub-components
function TuningWizard() {
  const navigation = useWizardNavigation();
  return (
    <div>
      <WizardHeader step={navigation.current} />
      <WizardStepContent step={navigation.current} />
      <WizardFooter onNext={navigation.next} onBack={navigation.back} />
    </div>
  );
}
```

### Step 7: Verify

After extraction:
- [ ] Parent component is under 300 lines
- [ ] Each sub-component is under 200 lines
- [ ] No prop drilling deeper than 2 levels
- [ ] All imports resolve correctly
- [ ] TypeScript compiles without errors
- [ ] UI renders identically (no visual changes)
- [ ] Feature directory has an `index.ts` if it exports 3+ components

## Common Extraction Patterns for DynoAI

### Wizard Step Pattern

Many DynoAI features use multi-step wizards. Extract each step:

```
components/jetdrive/
├── TuningWizard.tsx           (orchestrator, ~150 lines)
├── WizardStepConfig.tsx       (step 1: configuration)
├── WizardStepAnalysis.tsx     (step 2: analysis running)
├── WizardStepResults.tsx      (step 3: results review)
├── WizardStepApply.tsx        (step 4: apply/confirm)
└── WizardNavigation.tsx       (shared: step indicator + nav buttons)
```

### Data Table + Controls Pattern

Many pages have a table with filter/action controls:

```
components/<feature>/
├── <Feature>Page.tsx          (layout only)
├── <Feature>Table.tsx         (table rendering)
├── <Feature>Filters.tsx       (filter controls)
└── <Feature>Actions.tsx       (action buttons)
```

### Chart + Legend Pattern

Visualization components:

```
components/<feature>/
├── <Feature>Chart.tsx         (Recharts/D3 chart)
├── <Feature>Legend.tsx         (custom legend)
└── <Feature>Tooltip.tsx       (custom tooltip)
```

## Anti-Patterns to Avoid

1. **Don't create components for single elements** -- a `<Title>` that just renders an `<h1>` adds indirection without value.
2. **Don't split state that's inherently coupled** -- if two pieces of state always change together, keep them in the same hook/component.
3. **Don't create barrel exports prematurely** -- add `index.ts` only when a directory exports 3+ things.
4. **Don't change behavior during extraction** -- extraction should be a pure refactor with no functional changes.
