# Run Comparison Feature - Improvement Plan

## Overview

This document outlines improvements to the Run Comparison feature, ranging from quick wins to advanced enhancements. Each improvement includes implementation details, benefits, and priority level.

---

## 🚀 Quick Wins (1-2 hours each)

### 1. **Add Percentage Gains Display**

**Current**: Shows absolute deltas (+2.3 HP)
**Improved**: Show both absolute and percentage (+2.3 HP / +2.1%)

**Implementation**:
```typescript
const hpGainPercent = baseline.peak_hp > 0 
    ? ((run.peak_hp - baseline.peak_hp) / baseline.peak_hp) * 100 
    : 0;

<span className="text-[10px] text-green-400">
    +{hpGainPercent.toFixed(1)}%
</span>
```

**Benefits**:
- Easier to understand relative improvements
- Better for comparing different baseline power levels
- Industry standard metric

**Priority**: ⭐⭐⭐ High

---

### 2. **Add Run Notes/Tags**

**Feature**: Allow users to add notes to each run
- "After exhaust upgrade"
- "91 octane test"
- "Baseline tune"

**Implementation**:
```typescript
interface RunData {
    // ... existing fields
    notes?: string;
    tags?: string[];
}

// Add editable notes field in expanded row
<input 
    value={run.notes || ''} 
    onChange={(e) => updateRunNotes(run.run_id, e.target.value)}
    placeholder="Add notes..."
/>
```

**Benefits**:
- Track what changed between runs
- Better documentation
- Easier to identify specific runs later

**Priority**: ⭐⭐⭐ High

---

### 3. **Add "Best Run" Highlighting**

**Feature**: Automatically highlight the run with best HP/TQ

**Implementation**:
```typescript
const bestHpRun = compareRuns.reduce((best, run) => 
    run.peak_hp > best.peak_hp ? run : best
);

<TableRow className={`
    ${run === bestHpRun ? 'bg-green-500/10 border-green-500/30' : ''}
`}>
```

**Benefits**:
- Quick visual identification of best result
- Helps validate tuning progress
- Useful for customers/documentation

**Priority**: ⭐⭐ Medium

---

### 4. **Add Ambient Conditions Display**

**Feature**: Show temp/humidity/pressure if available

**Implementation**:
```typescript
interface RunData {
    // ... existing fields
    ambient?: {
        temperature_f?: number;
        humidity_percent?: number;
        pressure_inhg?: number;
    };
}

// Display in expanded row
<div className="text-xs text-zinc-500">
    🌡️ {ambient.temperature_f}°F • 
    💧 {ambient.humidity_percent}% • 
    🔽 {ambient.pressure_inhg}" Hg
</div>
```

**Benefits**:
- Explains performance variations
- Validates test consistency
- Professional documentation

**Priority**: ⭐⭐ Medium

---

## 📊 Visual Enhancements (2-4 hours each)

### 5. **Power Curve Overlay Chart** ✅ IMPLEMENTED

**Status**: Component created (`RunComparisonChart.tsx`)

**Features**:
- Overlay HP/TQ curves from multiple runs
- Color-coded lines (baseline is thicker/brighter)
- Interactive tooltips
- Zoom/pan capabilities

**Next Steps**:
- Integrate into JetDriveAutoTunePage
- Add toggle between HP/TQ/Both views
- Add power curve data to run manifests

**Benefits**:
- Visual comparison of entire power band
- Identify where gains/losses occur
- See if peak moved up/down RPM range

**Priority**: ⭐⭐⭐ High

---

### 6. **Sparkline Trends**

**Feature**: Mini charts showing HP trend across last 5 runs

**Implementation**:
```typescript
import { Sparklines, SparklinesLine } from 'react-sparklines';

<Sparklines data={last5Runs.map(r => r.peak_hp)} width={60} height={20}>
    <SparklinesLine color="#f97316" />
</Sparklines>
```

**Benefits**:
- Quick visual of tuning progress
- Spot trends at a glance
- Compact display

**Priority**: ⭐⭐ Medium

---

### 7. **Heatmap for VE Changes**

**Feature**: Show which VE cells changed most between runs

**Implementation**:
- Compare VE grids between runs
- Color cells by delta magnitude
- Red = got worse, Green = improved

**Benefits**:
- Identify problem areas
- Validate corrections applied
- Visual feedback on tuning effectiveness

**Priority**: ⭐⭐⭐ High

---

## 🎯 Advanced Features (4-8 hours each)

### 8. **Enhanced Run Selection** ✅ PARTIALLY IMPLEMENTED

**Status**: Component created (`RunComparisonTableEnhanced.tsx`)

**Features**:
- ✅ Checkbox selection for runs
- ✅ Custom baseline selection (star icon)
- ✅ Expandable rows with details
- ✅ Sortable columns
- ✅ CSV export

**Next Steps**:
- Integrate into main page
- Add multi-select actions (delete, tag, export)
- Save selection state in localStorage

**Benefits**:
- Compare any subset of runs
- Flexible baseline selection
- Better data exploration

**Priority**: ⭐⭐⭐ High

---

### 9. **Statistical Analysis**

**Feature**: Show statistical metrics across runs

**Metrics**:
- Average HP/TQ
- Standard deviation (consistency)
- Coefficient of variation
- Confidence intervals
- Trend line (linear regression)

**Implementation**:
```typescript
const stats = {
    avgHp: mean(runs.map(r => r.peak_hp)),
    stdDevHp: standardDeviation(runs.map(r => r.peak_hp)),
    cv: (stdDevHp / avgHp) * 100, // Lower = more consistent
};

<div className="text-xs">
    <div>Avg: {stats.avgHp.toFixed(1)} HP</div>
    <div>Std Dev: ±{stats.stdDevHp.toFixed(1)} HP</div>
    <div>Consistency: {stats.cv < 2 ? '✅ Excellent' : '⚠️ Variable'}</div>
</div>
```

**Benefits**:
- Validate test repeatability
- Identify outliers
- Professional analysis
- Data-driven decisions

**Priority**: ⭐⭐ Medium

---

### 10. **A/B Test Comparison**

**Feature**: Compare two specific runs in detail

**Layout**:
```
┌─────────────────────────────────────────┐
│  Run A          vs          Run B       │
├─────────────────────────────────────────┤
│  108.5 HP                 110.8 HP      │
│                +2.3 HP ↗                │
│  ─────────────────────────────────────  │
│  [Power Curve Overlay]                  │
│  ─────────────────────────────────────  │
│  VE Grid Side-by-Side                   │
│  ─────────────────────────────────────  │
│  AFR Trace Overlay                      │
└─────────────────────────────────────────┘
```

**Benefits**:
- Deep dive into two runs
- Perfect for before/after validation
- Detailed comparison

**Priority**: ⭐⭐ Medium

---

### 11. **Export Options**

**Formats**:
- ✅ CSV (basic data) - IMPLEMENTED
- PDF Report (formatted with charts)
- JSON (full data export)
- Excel (with formulas and charts)

**PDF Report Contents**:
- Cover page with summary
- Comparison table
- Power curve overlays
- VE heatmaps
- Notes and conclusions

**Implementation**:
```typescript
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

const exportToPDF = async () => {
    const pdf = new jsPDF();
    // Add title
    pdf.text('Dyno Run Comparison Report', 20, 20);
    // Capture charts as images
    const chartElement = document.getElementById('comparison-chart');
    const canvas = await html2canvas(chartElement);
    const imgData = canvas.toDataURL('image/png');
    pdf.addImage(imgData, 'PNG', 20, 40, 170, 100);
    // Save
    pdf.save('run_comparison.pdf');
};
```

**Benefits**:
- Professional documentation
- Share with customers
- Archive results
- Compliance/records

**Priority**: ⭐⭐⭐ High

---

### 12. **Run Grouping/Sessions**

**Feature**: Group related runs into tuning sessions

**Example**:
```
Session 1: "Initial Baseline" (3 runs)
Session 2: "VE Tuning" (5 runs)
Session 3: "Spark Optimization" (4 runs)
Session 4: "Final Validation" (2 runs)
```

**Benefits**:
- Organize complex tuning projects
- Track progress over multiple days
- Better documentation
- Easier to find specific runs

**Priority**: ⭐⭐ Medium

---

## 🔧 Technical Improvements

### 13. **Performance Optimization**

**Current Issues**:
- Fetching all run manifests can be slow
- No pagination for 100+ runs
- Table re-renders on every change

**Solutions**:
```typescript
// 1. Virtual scrolling for large lists
import { useVirtualizer } from '@tanstack/react-virtual';

// 2. Lazy loading of manifests
const { data } = useQuery({
    queryKey: ['run-manifest', runId],
    queryFn: () => fetchManifest(runId),
    enabled: isVisible, // Only fetch when row is visible
});

// 3. Memoization
const memoizedTable = useMemo(() => (
    <Table>...</Table>
), [compareRuns, baseline]);

// 4. Debounced search/filter
const debouncedFilter = useDebouncedValue(filterText, 300);
```

**Benefits**:
- Faster load times
- Smooth scrolling
- Better UX with many runs

**Priority**: ⭐⭐ Medium (when >50 runs)

---

### 14. **Caching Strategy**

**Implementation**:
```typescript
// Cache run data in IndexedDB
import { openDB } from 'idb';

const db = await openDB('dynoai-cache', 1, {
    upgrade(db) {
        db.createObjectStore('runs', { keyPath: 'run_id' });
    },
});

// Cache manifests locally
await db.put('runs', runData);

// Retrieve from cache first
const cached = await db.get('runs', runId);
if (cached && Date.now() - cached.timestamp < 3600000) {
    return cached;
}
```

**Benefits**:
- Offline access to run data
- Faster subsequent loads
- Reduced API calls

**Priority**: ⭐ Low (nice to have)

---

### 15. **Real-time Updates**

**Feature**: Auto-refresh when new runs complete

**Implementation**:
```typescript
// WebSocket or polling
const { data } = useQuery({
    queryKey: ['runs'],
    queryFn: fetchRuns,
    refetchInterval: 5000, // Poll every 5s
});

// Or WebSocket
useEffect(() => {
    const ws = new WebSocket('ws://localhost:5001/ws/runs');
    ws.onmessage = (event) => {
        const newRun = JSON.parse(event.data);
        queryClient.setQueryData(['runs'], (old) => [newRun, ...old]);
    };
}, []);
```

**Benefits**:
- Always up-to-date
- No manual refresh needed
- Better UX during active tuning

**Priority**: ⭐⭐ Medium

---

## 🎨 UI/UX Enhancements

### 16. **Responsive Mobile View**

**Current**: Table scrolls horizontally
**Improved**: Card-based layout on mobile

**Implementation**:
```typescript
// Mobile view (< 768px)
<div className="md:hidden">
    {runs.map(run => (
        <Card key={run.run_id}>
            <CardHeader>
                <CardTitle>{run.run_id}</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-2 gap-2">
                    <div>HP: {run.peak_hp}</div>
                    <div>TQ: {run.peak_tq}</div>
                </div>
            </CardContent>
        </Card>
    ))}
</div>

// Desktop view (>= 768px)
<div className="hidden md:block">
    <Table>...</Table>
</div>
```

**Benefits**:
- Better mobile experience
- Easier to use on tablets
- Professional on all devices

**Priority**: ⭐⭐ Medium

---

### 17. **Dark/Light Mode Toggle**

**Feature**: Support both color schemes

**Implementation**:
```typescript
// Use CSS variables
:root {
    --comparison-bg: #18181b;
    --comparison-text: #fafafa;
}

[data-theme="light"] {
    --comparison-bg: #ffffff;
    --comparison-text: #09090b;
}

// Apply in components
className="bg-[var(--comparison-bg)] text-[var(--comparison-text)]"
```

**Benefits**:
- User preference support
- Better accessibility
- Modern UX

**Priority**: ⭐ Low (if app-wide theme exists)

---

### 18. **Keyboard Shortcuts**

**Shortcuts**:
- `Ctrl+E` - Export CSV
- `Ctrl+A` - Select all runs
- `↑/↓` - Navigate runs
- `Space` - Toggle selection
- `Enter` - View details

**Implementation**:
```typescript
useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
        if (e.ctrlKey && e.key === 'e') {
            e.preventDefault();
            exportToCSV();
        }
        // ... other shortcuts
    };
    
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

**Benefits**:
- Power user efficiency
- Professional feel
- Faster workflow

**Priority**: ⭐ Low (nice to have)

---

## 📈 Data Analysis Features

### 19. **Trend Analysis**

**Feature**: Show trends over time

**Visualizations**:
- HP trend line (linear regression)
- Moving average (3-run, 5-run)
- Forecast next expected HP
- Identify plateaus

**Implementation**:
```typescript
import regression from 'regression';

const hpData = runs.map((r, i) => [i, r.peak_hp]);
const result = regression.linear(hpData);

// Trend line equation: y = mx + b
const slope = result.equation[0];
const intercept = result.equation[1];

// Forecast next run
const nextRunHp = slope * runs.length + intercept;

<div className="text-xs text-zinc-500">
    Trend: {slope > 0 ? '📈' : '📉'} 
    {Math.abs(slope).toFixed(2)} HP per run
    <br />
    Projected next: {nextRunHp.toFixed(1)} HP
</div>
```

**Benefits**:
- Understand tuning progress
- Predict outcomes
- Know when to stop (plateau reached)
- Data-driven decisions

**Priority**: ⭐⭐ Medium

---

### 20. **Anomaly Detection**

**Feature**: Flag suspicious runs

**Checks**:
- HP/TQ outside 2 standard deviations
- Duration too short/long
- AFR wildly different
- VE corrections too aggressive

**Implementation**:
```typescript
const isAnomaly = (run: RunData, baseline: Stats) => {
    const hpZScore = Math.abs((run.peak_hp - baseline.avgHp) / baseline.stdDevHp);
    const tqZScore = Math.abs((run.peak_tq - baseline.avgTq) / baseline.stdDevTq);
    
    return hpZScore > 2 || tqZScore > 2;
};

{isAnomaly(run, stats) && (
    <Badge variant="destructive" className="text-xs">
        ⚠️ Anomaly
    </Badge>
)}
```

**Benefits**:
- Catch bad data
- Identify test issues
- Improve data quality
- Avoid bad decisions

**Priority**: ⭐⭐ Medium

---

## 🔌 Integration Features

### 21. **Share/Collaborate**

**Feature**: Share comparison with others

**Options**:
- Generate shareable link
- Email report
- Cloud save/sync
- Team collaboration

**Implementation**:
```typescript
const shareComparison = async () => {
    const shareData = {
        runs: compareRuns,
        baseline: baseline.run_id,
        notes: userNotes,
    };
    
    const response = await fetch('/api/share/comparison', {
        method: 'POST',
        body: JSON.stringify(shareData),
    });
    
    const { shareId } = await response.json();
    const shareUrl = `${window.location.origin}/share/${shareId}`;
    
    // Copy to clipboard
    navigator.clipboard.writeText(shareUrl);
    toast.success('Share link copied!');
};
```

**Benefits**:
- Collaborate with team
- Get remote help
- Share with customers
- Professional service

**Priority**: ⭐ Low (requires backend)

---

### 22. **Integration with Tuning Software**

**Feature**: Export directly to Power Vision, EFI Live, etc.

**Formats**:
- Power Vision .pvv (already supported)
- EFI Live .tun
- HP Tuners .hpt
- Dynojet .djm

**Benefits**:
- Streamlined workflow
- No manual data entry
- Professional integration
- Time savings

**Priority**: ⭐⭐ Medium

---

## 📋 Implementation Priority

### Phase 1 - Quick Wins (Week 1)
1. ✅ Percentage gains display
2. ✅ Run notes/tags
3. ✅ Best run highlighting
4. ✅ Ambient conditions

### Phase 2 - Visual Enhancements (Week 2)
5. ✅ Power curve overlay chart (DONE)
6. Integrate chart into main page
7. Sparkline trends
8. VE change heatmap

### Phase 3 - Advanced Features (Week 3-4)
9. ✅ Enhanced run selection (DONE)
10. Integrate enhanced table
11. Statistical analysis
12. A/B test comparison
13. PDF export

### Phase 4 - Polish (Week 5)
14. Performance optimization
15. Real-time updates
16. Responsive mobile view
17. Keyboard shortcuts

### Phase 5 - Analytics (Week 6)
18. Trend analysis
19. Anomaly detection
20. Forecasting

### Phase 6 - Integration (Future)
21. Share/collaborate
22. Tuning software integration

---

## 🎯 Recommended Next Steps

### Immediate (This Week)
1. **Integrate RunComparisonChart** - Add power curve overlay
2. **Add percentage gains** - Quick win, high value
3. **Implement run notes** - User requested feature

### Short Term (Next 2 Weeks)
4. **Integrate RunComparisonTableEnhanced** - Better UX
5. **Add PDF export** - Professional documentation
6. **Statistical analysis** - Data-driven tuning

### Long Term (Next Month)
7. **Performance optimization** - As data grows
8. **Mobile responsiveness** - Broader device support
9. **Trend analysis** - Advanced insights

---

## 📊 Success Metrics

Track these metrics to measure improvement success:

1. **User Engagement**
   - % of users using comparison feature
   - Average runs compared per session
   - Time spent in comparison view

2. **Feature Adoption**
   - Export usage (CSV, PDF)
   - Notes/tags added
   - Custom baseline selections

3. **Performance**
   - Load time for comparison table
   - Time to first paint
   - Scroll performance

4. **User Satisfaction**
   - Feature ratings
   - Support tickets related to comparison
   - User feedback/requests

---

## 🤝 Contributing

Want to implement one of these improvements? Here's how:

1. Pick a feature from the list
2. Create a feature branch: `feature/comparison-{feature-name}`
3. Implement with tests
4. Update documentation
5. Submit PR with screenshots/demo

**Questions?** Open an issue or discussion!

---

**Last Updated**: December 15, 2025
**Status**: Living document - will be updated as features are implemented

