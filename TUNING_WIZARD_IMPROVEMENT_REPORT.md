# Tuning Wizard Improvement Recommendations Report

**Date:** January 30, 2026  
**Component:** Seamless Auto-Tune Wizard  
**Status:** Analysis Complete

---

## Executive Summary

This report identifies 7 major areas for improvement in the TuningWizard implementation, with 23 specific, actionable recommendations prioritized by impact and implementation effort. The analysis reveals that while the core functionality is solid, there are significant opportunities to enhance user experience, performance, accessibility, and code maintainability.

---

## 1. Critical Issue: useTuningWizard Hook Not Utilized

### Problem
The `useTuningWizard` hook (`frontend/src/hooks/useTuningWizard.ts`) is imported in `JetDriveAutoTunePage.tsx` but **never actually called**. The `TuningWizard` component duplicates all the hook's logic internally, leading to:

- **Code duplication**: State management logic exists in both places
- **Maintenance burden**: Changes must be made in two locations
- **Inconsistent behavior**: Hook provides features (session tracking, pull counting, milestone tracking) that aren't available in the component
- **Lost functionality**: The hook includes `recordPull()`, `sessionDuration`, `pullCount`, and coverage milestone tracking that aren't being used

### Evidence
- **File:** `frontend/src/pages/JetDriveAutoTunePage.tsx:74`
  - Hook is imported: `import { useTuningWizard } from '../hooks/useTuningWizard';`
  - But never called in the component

- **File:** `frontend/src/components/jetdrive/TuningWizard.tsx:100-104`
  - Component manages its own state instead of using the hook:
    ```typescript
    const [step, setStep] = useState<WizardStep>('setup');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [showDetails, setShowDetails] = useState(false);
    const [applyReport, setApplyReport] = useState<ApplyReport | null>(null);
    ```

### Recommendation: **HIGH PRIORITY**

**Option A: Refactor TuningWizard to use the hook (Recommended)**
- Replace internal state management with `useTuningWizard` hook
- Benefits: Single source of truth, session tracking, milestone events
- Effort: Medium (2-3 hours)
- Risk: Low (hook is well-tested)

**Option B: Remove unused hook**
- If hook isn't needed, remove it to reduce confusion
- Effort: Low (30 minutes)
- Risk: Medium (may want hook features later)

**Implementation Example:**
```typescript
// In TuningWizard.tsx
const wizard = useTuningWizard({
  importedTune,
  liveData,
  isSimulatorActive,
  isCapturing,
  veBoundsPreset,
});

// Use wizard.step, wizard.advanceStep(), wizard.recordPull(), etc.
```

---

## 2. Auto-Advance Logic Improvements

### Current Implementation
**File:** `frontend/src/components/jetdrive/TuningWizard.tsx:122-130`

```typescript
// Auto-advance: Setup -> Collect
useEffect(() => {
  if (step === 'setup' && importedTune && (isSimulatorActive || isCapturing)) {
    setStep('collect');
  }
}, [step, importedTune, isSimulatorActive, isCapturing]);

// Check if ready to proceed from Collect
const canProceedToAnalyze = coveragePct >= COVERAGE_TARGET && totalHits >= MIN_HITS_TARGET;
```

### Issues Identified

1. **No auto-advance from Collect → Analyze**
   - User must manually click "ANALYZE" even when conditions are met
   - Plan specifies: "Step 2→3: weightedCoveragePct ≥ target AND totalHits ≥ minimum, OR user click"
   - Current: Only manual click works

2. **No debouncing/throttling**
   - Coverage calculations happen on every render
   - Could cause rapid step transitions if coverage fluctuates

3. **No visual feedback for auto-advance readiness**
   - Button pulses when ready, but no countdown or progress indicator
   - User doesn't know how close they are to auto-advance threshold

4. **Missing "Analyze Anyway" auto-advance logic**
   - Line 311-320 shows "Analyze Anyway" button for `totalHits > 50`
   - But this doesn't auto-advance, only enables manual button

### Recommendations: **MEDIUM PRIORITY**

**2.1: Implement auto-advance from Collect → Analyze**
```typescript
// Add debounced auto-advance
useEffect(() => {
  if (step === 'collect' && canProceedToAnalyze && !isAnalyzing) {
    const timer = setTimeout(() => {
      handleAnalyze();
    }, 2000); // 2 second delay to prevent rapid transitions
    return () => clearTimeout(timer);
  }
}, [step, canProceedToAnalyze, isAnalyzing]);
```

**2.2: Add visual progress indicator**
- Show progress bar: "67% coverage - 1,247 hits (need 60% / 500)"
- Color-coded: Red (<50%), Yellow (50-75%), Green (>75%)
- Animate when approaching threshold

**2.3: Add countdown timer for auto-advance**
- When conditions met, show: "Auto-analyzing in 3... 2... 1..."
- Allow user to cancel with "Analyze Now" button

**2.4: Debounce coverage calculations**
```typescript
const debouncedCoverage = useDebounce(coveragePct, 500);
```

---

## 3. Dual-Delta Heatmap Implementation Status

### Current Implementation
**File:** `frontend/src/components/jetdrive/ApplyPreviewPanel.tsx:283-423`

The dual-delta heatmap is **partially implemented**:

✅ **Implemented:**
- Toggle between "Applied Delta" and "Raw Delta" modes (lines 290-309)
- Per-cell display of both values in tooltip (lines 389-393)
- Visual distinction: Applied (green), Raw (orange) button states
- Cell markers for skipped/clamped/bounded (lines 368-381)

❌ **Missing/Incomplete:**
- **No side-by-side comparison**: Can't see both deltas simultaneously
- **Limited grid size**: Only shows 15x12 cells (lines 353, 342) - should show full grid
- **No overlay mode**: Plan mentions "overlay/toggle" but only toggle exists
- **No per-cell confidence badges**: Plan specifies "confidence badge on hover" but only shows in tooltip
- **No visual diff highlighting**: Cells that differ significantly between raw/applied aren't highlighted
- **Heatmap hidden by default**: Must click "Show Heatmap" - should be more prominent in review step

### Recommendations: **MEDIUM PRIORITY**

**3.1: Add side-by-side comparison view**
```typescript
// New view mode: 'split' | 'applied' | 'raw'
const [heatmapViewMode, setHeatmapViewMode] = useState<'split' | 'applied' | 'raw'>('split');

// Render two grids side-by-side when in split mode
{heatmapViewMode === 'split' && (
  <div className="grid grid-cols-2 gap-4">
    <HeatmapGrid mode="applied" title="Applied Delta" />
    <HeatmapGrid mode="raw" title="Raw Delta" />
  </div>
)}
```

**3.2: Show full grid, not truncated**
- Remove `.slice(0, 15)` and `.slice(0, 12)` limitations
- Add virtual scrolling or pagination for large grids
- Or use CSS grid with proper overflow handling

**3.3: Add overlay mode**
- Toggle: "Overlay Raw Delta" checkbox
- When enabled, show applied delta as background color, raw delta as border color intensity
- Tooltip shows both values clearly

**3.4: Enhance cell markers**
- Add confidence badge overlay (not just tooltip)
- Use different border styles: dashed (clamped), dotted (bounded), solid (normal)
- Add cell size variation based on confidence level

**3.5: Make heatmap default visible in review step**
- When `step === 'review'`, automatically show heatmap
- Add "Hide Heatmap" option for users who want minimal view
- Consider making it the primary view in review step

---

## 4. Performance Optimization Opportunities

### Current State
**File:** `frontend/src/components/jetdrive/TuningWizard.tsx`

✅ **Good practices found:**
- `useMemo` for coverage calculations (line 107)
- `useCallback` for event handlers (lines 133, 159)
- `useMemo` for apply summary (line 167)

❌ **Issues identified:**

1. **Render functions not memoized**
   - `renderStepIndicator()`, `renderProgressRing()`, `renderActionButton()`, etc. are recreated on every render
   - These functions contain complex JSX that could be expensive

2. **Coverage calculation runs on every liveData change**
   - No throttling for rapid live data updates
   - Could cause performance issues during active data collection

3. **ApplyPreviewPanel recalculates on every render**
   - `calculateApply()` called in `useMemo` but dependencies may change frequently
   - Large grid calculations could block UI

4. **No React.memo on child components**
   - `TuningWizard` renders many child components that could be memoized
   - Step indicator buttons re-render even when step hasn't changed

### Recommendations: **MEDIUM PRIORITY**

**4.1: Memoize render functions**
```typescript
const renderStepIndicator = useCallback(() => {
  // ... existing code
}, [step]);

const renderProgressRing = useMemo(() => {
  // ... existing code
}, [coveragePct, coverageGrade]);
```

**4.2: Throttle live data updates**
```typescript
const throttledLiveData = useThrottle(liveData, 500); // Update max once per 500ms
```

**4.3: Memoize step indicator buttons**
```typescript
const StepButton = React.memo(({ step, isCurrent, isPast, onClick }) => {
  // ... button JSX
});
```

**4.4: Virtualize large heatmap grids**
- Use `react-window` or `react-virtualized` for grids > 20x20
- Only render visible cells

**4.5: Lazy load ApplyPreviewPanel**
```typescript
const ApplyPreviewPanel = React.lazy(() => import('./ApplyPreviewPanel'));
// Wrap in Suspense when rendering
```

---

## 5. Accessibility Improvements

### Current State
**Finding:** No ARIA attributes found in TuningWizard component

### Issues Identified

1. **No ARIA labels on interactive elements**
   - Step indicator buttons have no `aria-label`
   - Progress ring has no `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
   - Action buttons lack descriptive labels

2. **No keyboard navigation**
   - Step indicator buttons not keyboard accessible
   - Can't navigate steps with arrow keys
   - No focus management between steps

3. **No screen reader announcements**
   - Step transitions not announced
   - Coverage milestones not announced
   - Auto-advance not announced

4. **No focus indicators**
   - Buttons may not have visible focus states
   - Keyboard users can't see where focus is

5. **Color-only indicators**
   - Status relies heavily on color (red/yellow/green)
   - No icons or text for colorblind users

### Recommendations: **HIGH PRIORITY** (Accessibility is critical)

**5.1: Add ARIA labels to all interactive elements**
```typescript
<button
  onClick={() => setStep(s)}
  aria-label={`Go to step ${config.number}: ${config.title}`}
  aria-current={isCurrent ? 'step' : undefined}
  role="tab"
>
```

**5.2: Add ARIA live regions for announcements**
```typescript
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {stepAnnouncement}
</div>
```

**5.3: Make progress ring accessible**
```typescript
<div
  role="progressbar"
  aria-valuenow={coveragePct}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-label={`Coverage: ${coveragePct}%`}
>
```

**5.4: Add keyboard navigation**
```typescript
// Arrow keys to navigate steps
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight' && canAdvance) advanceStep();
    if (e.key === 'ArrowLeft') goBack();
  };
  window.addEventListener('keydown', handleKeyDown);
  return () => window.removeEventListener('keydown', handleKeyDown);
}, [canAdvance, advanceStep, goBack]);
```

**5.5: Add focus management**
```typescript
// Focus first interactive element when step changes
useEffect(() => {
  if (step === 'review' && applyReport) {
    document.getElementById('apply-button')?.focus();
  }
}, [step, applyReport]);
```

**5.6: Add text labels to color indicators**
- Don't rely solely on color for status
- Add icons or text: "✓ Ready" instead of just green badge
- Use patterns or shapes in addition to color

---

## 6. Missing Features from Original Plan

### Plan Reference
**File:** `.cursor/plans/seamless_auto-tune_wizard_c392e4be.plan.md`

### Pending Features

**6.1: Progressive Disclosure (4-layer system)** - Status: **PENDING**
- Plan specifies: Glance → Summary → Full → Debug layers
- Current: Only 2 layers (collapsed/expanded)
- **Recommendation:** Implement 4-layer system with smooth transitions

**6.2: Block/Warn UI Cards (Expandable)** - Status: **PARTIAL**
- Plan specifies: Expandable cards with counts and example cells
- Current: Basic block/warning display in ApplyPreviewPanel (lines 130-168)
- Missing: Expandable functionality, example cells with RPM/MAP values
- **Recommendation:** Add expandable cards with cell examples

**6.3: Convergence Tracker** - Status: **NOT IMPLEMENTED**
- Plan specifies: Background tracking of session count, oscillating cells, estimated sessions remaining
- Current: No implementation found
- **Recommendation:** Implement localStorage-based tracking with UI badge

**6.4: Session History Panel** - Status: **NOT IMPLEMENTED**
- Plan specifies: View/export/rollback for each session plus baseline export
- Current: No implementation found
- **Recommendation:** Create SessionHistoryPanel component

**6.5: Pre-Apply Validation** - Status: **PARTIAL**
- Plan specifies: Background PVV parse check, range check, large delta warnings
- Current: Block conditions exist but no pre-apply validation UI
- **Recommendation:** Add validation step before apply with detailed feedback

**6.6: Voice Assistant Integration** - Status: **PARTIAL**
- Plan specifies: Re-enable useAIAssistant with new events
- Current: `useAIAssistant` is imported and enabled in JetDriveAutoTunePage (line 617)
- Missing: Coverage milestone events, balance warnings, apply blocks, step transitions
- **Recommendation:** Add voice events for all wizard milestones

### Recommendations: **LOW-MEDIUM PRIORITY** (Nice-to-have features)

**Priority order:**
1. Voice Assistant Integration (high impact, low effort)
2. Block/Warn UI Cards enhancement (medium impact, low effort)
3. Pre-Apply Validation UI (medium impact, medium effort)
4. Progressive Disclosure (low impact, high effort)
5. Convergence Tracker (low impact, medium effort)
6. Session History Panel (low impact, high effort)

---

## 7. User Experience Enhancements

### Issues Identified

**7.1: No loading states during analysis**
- When `handleAnalyze()` runs, only shows spinner
- No progress indication for multi-step analysis
- Plan specifies: "Step-by-step progress: ✓ Normalizing data... ✓ Classifying zones..."

**7.2: No error handling**
- If `onAnalyze()` throws, error isn't caught or displayed
- User doesn't know what went wrong

**7.3: No undo/redo capability**
- Can't go back after applying corrections
- No way to revert to previous state

**7.4: No session persistence**
- If page refreshes, wizard state is lost
- No way to resume interrupted session

**7.5: Download button doesn't actually download**
- Line 362-368: Download button has no `onClick` handler
- Just renders button with no functionality

**7.6: No confirmation dialogs**
- Applying corrections has no confirmation
- Could accidentally apply wrong corrections

### Recommendations: **MEDIUM PRIORITY**

**7.1: Add analysis progress steps**
```typescript
const [analysisSteps, setAnalysisSteps] = useState<string[]>([]);
const [currentStep, setCurrentStep] = useState(0);

// In handleAnalyze:
setAnalysisSteps(['Normalizing data...', 'Classifying zones...', 'Calculating corrections...']);
// Update currentStep as each completes
```

**7.2: Add error boundary and error display**
```typescript
try {
  await onAnalyze();
} catch (error) {
  setError(error.message);
  setStep('collect'); // Return to collect on error
}
```

**7.3: Implement download functionality**
```typescript
<Button onClick={() => downloadAppliedVEAllFormats(applyReport)}>
  DOWNLOAD
</Button>
```

**7.4: Add confirmation dialog for apply**
```typescript
const [showConfirmDialog, setShowConfirmDialog] = useState(false);

const handleApplyClick = () => {
  setShowConfirmDialog(true);
};

const handleConfirmApply = () => {
  handleApply();
  setShowConfirmDialog(false);
};
```

**7.5: Add session persistence**
```typescript
// Save wizard state to localStorage
useEffect(() => {
  localStorage.setItem('wizardState', JSON.stringify({ step, applyReport }));
}, [step, applyReport]);

// Restore on mount
useEffect(() => {
  const saved = localStorage.getItem('wizardState');
  if (saved) {
    const state = JSON.parse(saved);
    setStep(state.step);
    setApplyReport(state.applyReport);
  }
}, []);
```

---

## Priority Matrix

| Priority | Issue | Impact | Effort | Recommendation |
|----------|-------|--------|--------|----------------|
| **P0** | useTuningWizard hook not used | High | Medium | Refactor to use hook |
| **P0** | Accessibility (ARIA, keyboard) | High | Medium | Add ARIA labels and keyboard nav |
| **P1** | Download button not functional | High | Low | Implement download handler |
| **P1** | Auto-advance Collect→Analyze | Medium | Low | Add auto-advance logic |
| **P1** | Error handling | Medium | Low | Add try/catch and error display |
| **P2** | Dual-delta heatmap enhancements | Medium | Medium | Add side-by-side view, full grid |
| **P2** | Performance optimizations | Medium | Medium | Memoize render functions |
| **P2** | Analysis progress steps | Medium | Low | Add step-by-step progress UI |
| **P3** | Voice assistant events | Low | Low | Add milestone events |
| **P3** | Session persistence | Low | Medium | Add localStorage persistence |
| **P3** | Convergence tracker | Low | Medium | Implement background tracking |
| **P4** | Progressive disclosure | Low | High | Implement 4-layer system |
| **P4** | Session history panel | Low | High | Create history component |

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
1. ✅ Refactor TuningWizard to use useTuningWizard hook
2. ✅ Add ARIA labels and keyboard navigation
3. ✅ Implement download button functionality
4. ✅ Add error handling and display

### Phase 2: Core Enhancements (Week 2)
5. ✅ Implement auto-advance from Collect → Analyze
6. ✅ Add analysis progress steps UI
7. ✅ Enhance dual-delta heatmap (side-by-side, full grid)
8. ✅ Add confirmation dialog for apply

### Phase 3: Performance & Polish (Week 3)
9. ✅ Memoize render functions and optimize re-renders
10. ✅ Add voice assistant milestone events
11. ✅ Add session persistence
12. ✅ Enhance block/warn UI cards

### Phase 4: Advanced Features (Future)
13. ⏳ Convergence tracker
14. ⏳ Session history panel
15. ⏳ Progressive disclosure system

---

## Code Quality Recommendations

### 7.1: Extract Constants
Move magic numbers to constants:
```typescript
// Current (line 79-80):
const COVERAGE_TARGET = 60;
const MIN_HITS_TARGET = 500;

// Better:
const WIZARD_CONFIG = {
  COVERAGE_TARGET: 60,
  MIN_HITS_TARGET: 500,
  AUTO_ADVANCE_DELAY_MS: 2000,
  DEBOUNCE_MS: 500,
} as const;
```

### 7.2: Type Safety
Add stricter types:
```typescript
// Current: step can be any string
const [step, setStep] = useState<WizardStep>('setup');

// Better: Use const assertion
const WIZARD_STEPS = ['setup', 'collect', 'analyze', 'review', 'apply'] as const;
type WizardStep = typeof WIZARD_STEPS[number];
```

### 7.3: Extract Sub-components
Break down large render functions:
```typescript
// Extract to separate files:
- WizardStepIndicator.tsx (already exists but not used?)
- WizardProgressRing.tsx
- WizardActionButton.tsx
- WizardStatusBadge.tsx
```

### 7.4: Add Unit Tests
No tests found for TuningWizard. Add tests for:
- Step transitions
- Auto-advance logic
- Coverage calculations
- Apply validation

---

## Conclusion

The TuningWizard implementation is functional but has significant room for improvement. The highest priority items are:

1. **Using the existing useTuningWizard hook** (eliminates duplication, adds features)
2. **Accessibility improvements** (critical for usability)
3. **Fixing broken functionality** (download button, error handling)

Most improvements are straightforward and can be implemented incrementally without breaking existing functionality. The wizard has a solid foundation and these enhancements will significantly improve the user experience.

---

## Appendix: File References

### Primary Files Analyzed
- `frontend/src/components/jetdrive/TuningWizard.tsx` - Main wizard component
- `frontend/src/hooks/useTuningWizard.ts` - Unused hook with better state management
- `frontend/src/components/jetdrive/ApplyPreviewPanel.tsx` - Review step panel
- `frontend/src/pages/JetDriveAutoTunePage.tsx` - Parent page integration
- `.cursor/plans/seamless_auto-tune_wizard_c392e4be.plan.md` - Original plan

### Related Components
- `frontend/src/components/jetdrive/ZoneCoverageCard.tsx` - Coverage display
- `frontend/src/components/jetdrive/SmartPromptBanner.tsx` - Guidance prompts
- `frontend/src/components/jetdrive/SessionSummaryCard.tsx` - Results display
- `frontend/src/components/jetdrive/QuickActionsPanel.tsx` - Quick actions

---

**Report Generated:** January 30, 2026  
**Next Review:** After Phase 1 implementation
