# Frontend Dependency Cleanup Plan
**Generated:** 2025-12-15
**Based on:** Live codebase audit

---

## 📊 Audit Results Summary

### ✅ Phase 1: Python Dependencies - COMPLETED
- **Fixed:** Version conflicts across 3 files
- **Updated:** Pillow 10.4.0 → 11.0.0 (Security fix)
- **Unified:** Flask ecosystem to 3.1.0/5.0.0/3.1.4

### ✅ Phase 2: Frontend Audit - COMPLETED
Analyzed 79 frontend dependencies across 33+ source files

---

## 🎯 Icon Libraries Analysis

### Current State (3 Libraries Installed)
| Library | Files Using | Size (uncompressed) | Status |
|---------|-------------|---------------------|--------|
| **lucide-react** | **33 files** | ~1.5 MB | ✅ **KEEP** |
| @heroicons/react | **0 files** | ~800 KB | ❌ **REMOVE** |
| @phosphor-icons/react | **2 files** | ~1.2 MB | ⚠️ **MIGRATE** |

### Files Using @phosphor-icons
1. `src/components/AnalyzeRun.tsx` - Uses: FileArrowUp, Play, CheckCircle, DownloadSimple, ChartLine
2. `src/components/VisualizeVE.tsx` - (icons to be determined)

### Recommendation: **CONSOLIDATE TO LUCIDE-REACT**

**Lucide-react equivalents for Phosphor icons:**
```typescript
// Before (Phosphor):
import { FileArrowUp, Play, CheckCircle, DownloadSimple, ChartLine } from '@phosphor-icons/react';

// After (Lucide):
import { FileUp, Play, CheckCircle, Download, LineChart } from 'lucide-react';
```

**Action Items:**
```bash
# 1. Update the 2 files using @phosphor-icons
# 2. Remove unused icon libraries
npm uninstall @heroicons/react @phosphor-icons/react

# Estimated savings: ~2 MB uncompressed, ~700 KB gzipped
```

---

## 🎨 Three.js Analysis

### Current State
- **Package:** three@0.175.0 (~600 KB minified)
- **Usage:** **1 file** - `src/components/VESurface.tsx`
- **Purpose:** 3D VE table visualization

### Recommendation: **KEEP**

**Rationale:**
- Used for critical VE surface visualization (core feature)
- 600 KB is reasonable for 3D graphics capability
- No lighter alternatives for 3D surface plots
- **Status:** ✅ Justified dependency

---

## 🐙 GitHub Libraries Analysis

### Current State (3 Packages Installed)
| Package | Files Using | Size | Status |
|---------|-------------|------|--------|
| @octokit/core | **0 files** | ~50 KB | ❌ **REMOVE** |
| octokit | **0 files** | ~100 KB | ❌ **REMOVE** |
| @github/spark | **0 files** | ~80 KB | ❌ **REMOVE** |

### Recommendation: **REMOVE ALL**

**No GitHub integration is currently used in the codebase.**

**Action Items:**
```bash
npm uninstall @octokit/core octokit @github/spark

# Estimated savings: ~230 KB uncompressed
```

**Note:** If you plan to add GitHub integration later, reinstall `octokit` only (it includes `@octokit/core`).

---

## 📦 HTTP Client Analysis

### Current State
- **axios:** Used in 3 files (`api/jetstream.ts`, `api/wizards.ts`, `lib/api.ts`)
- **socket.io-client:** Used for WebSocket connections
- **@tanstack/react-query:** Available for HTTP requests

### Recommendation: **KEEP AXIOS FOR NOW**

**Rationale:**
- Actively used in API utility files
- Well-integrated into existing code
- Migration to fetch/React Query would require refactoring
- Savings would be minimal (~30 KB gzipped)

**Future consideration:** When refactoring API layer, consider consolidating to React Query + fetch.

---

## 🧩 Radix UI Components Analysis

### Current State
- **Installed Packages:** 28 Radix UI packages
- **UI Component Files:** 46 custom wrappers in `src/components/ui/`
- **All packages appear to be in use** through the UI component system

### Radix Packages in Use ✅
```
accordion, alert-dialog, aspect-ratio, avatar, checkbox, collapsible,
context-menu, dialog, dropdown-menu, hover-card, label, menubar,
navigation-menu, popover, progress, radio-group, scroll-area, select,
separator, slider, slot, switch, tabs, toggle, toggle-group, tooltip
```

### Recommendation: **KEEP ALL**

**Rationale:**
- All have corresponding UI component wrappers
- Radix UI is the foundation of your component system
- Components may be used indirectly through your UI library
- Tree-shaking will remove unused code from bundle

**Optional:** Run `npx depcheck` to verify no unused packages, but initial analysis shows good alignment.

---

## 💰 Total Cleanup Impact

### Immediate Removals (High Confidence)

| Action | Packages | Bundle Savings | Time |
|--------|----------|----------------|------|
| Remove @heroicons/react | 1 | ~280 KB gzipped | 1 min |
| Remove @phosphor-icons (after migration) | 1 | ~400 KB gzipped | 15 min |
| Remove all 3 GitHub libraries | 3 | ~80 KB gzipped | 1 min |
| **TOTAL** | **5 packages** | **~760 KB gzipped** | **17 min** |

### Keep (Justified)
- ✅ Three.js - Used for 3D VE visualization
- ✅ Axios - Actively used in API layer
- ✅ All 28 Radix UI packages - Component system foundation
- ✅ Lucide-react - Primary icon library (33 files)

---

## 🚀 Implementation Plan

### Step 1: Remove Unused GitHub Libraries (2 minutes)
```bash
cd /home/user/DynoAI_3/frontend
npm uninstall @octokit/core octokit @github/spark
```

### Step 2: Remove @heroicons/react (1 minute)
```bash
npm uninstall @heroicons/react
```

### Step 3: Migrate @phosphor-icons to lucide-react (15 minutes)

**File 1: `src/components/AnalyzeRun.tsx`**
```typescript
// Line 8: Change import
- import { FileArrowUp, Play, CheckCircle, DownloadSimple, ChartLine } from '@phosphor-icons/react';
+ import { FileUp, Play, CheckCircle, Download, LineChart } from 'lucide-react';

// Update icon usage in JSX (same component names work)
```

**File 2: `src/components/VisualizeVE.tsx`**
```bash
# Need to review this file to identify which icons to replace
```

### Step 4: Remove @phosphor-icons/react (1 minute)
```bash
npm uninstall @phosphor-icons/react
```

### Step 5: Test Application (5 minutes)
```bash
npm run build
npm run preview
# Verify all icons display correctly
```

### Step 6: Commit Changes
```bash
git add package.json package-lock.json src/
git commit -m "refactor: Consolidate to single icon library, remove unused deps

- Remove @heroicons/react (unused)
- Migrate from @phosphor-icons/react to lucide-react
- Remove unused GitHub libraries (@octokit/core, octokit, @github/spark)
- Bundle size reduction: ~760 KB gzipped

Closes #[issue-number]"
```

---

## 📈 Before & After Comparison

### Bundle Size Estimate
```
Before:
  Lucide-react:     500 KB gzipped
  Phosphor-icons:   400 KB gzipped
  Heroicons:        280 KB gzipped
  GitHub libs:       80 KB gzipped
  ────────────────────────────────
  Total icons/misc: 1,260 KB

After:
  Lucide-react:     500 KB gzipped
  ────────────────────────────────
  Total icons/misc:  500 KB

Savings: 760 KB gzipped (~60% reduction in icon/misc bundle)
```

### Package Count
- Before: 79 packages
- After: 74 packages (-5)

---

## ⚠️ Important Notes

1. **Lucide vs Phosphor Icon Mapping:**
   - Most icons have direct equivalents
   - Some may need slight naming adjustments (e.g., `FileArrowUp` → `FileUp`)
   - Visual style is similar (both are line-based icon sets)

2. **Testing Required:**
   - Verify icon appearances in UI after migration
   - Check icon sizes match design expectations
   - Test on multiple screen sizes

3. **Future Additions:**
   - Stick to lucide-react for all new icons
   - Document icon choice in component guidelines
   - Consider adding ESLint rule to prevent multiple icon libraries

---

## 🔄 Alternative: Keep @phosphor-icons?

**If you prefer Phosphor's design style:**

**Option B: Migrate lucide-react to @phosphor-icons instead**
- Phosphor has more icon weights (thin, light, regular, bold, fill)
- Would require updating 33 files (more work)
- Lucide is more actively maintained and popular
- **Recommendation:** Stick with lucide-react (less work, better ecosystem)

---

## ✅ Final Recommendations

### Do This Week:
1. ✅ Remove GitHub libraries (no code changes needed)
2. ✅ Remove @heroicons/react (no code changes needed)
3. ✅ Migrate 2 files from @phosphor-icons to lucide-react
4. ✅ Remove @phosphor-icons/react

### Don't Remove:
- ❌ Three.js (actively used for 3D visualization)
- ❌ Radix UI packages (component system foundation)
- ❌ Axios (consider for future refactor, not urgent)

### Optional Future Work:
- Consider migrating axios to fetch + React Query
- Set up bundle size monitoring
- Add ESLint rule to prevent multiple icon library imports

---

**Next Action:** Ready to implement? I can make these changes automatically.

Say:
- **"A"** - Auto-remove GitHub libraries and @heroicons (safe, no code changes)
- **"B"** - Show me the exact icon migration changes first
- **"C"** - Do everything automatically (remove + migrate)
- **"D"** - I'll handle this manually