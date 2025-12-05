# VE Heatmap Implementation Guide

**Status**: 🟡 **Ready to Implement** (All components exist, just need integration)  
**Estimated Time**: 30-60 minutes  
**Difficulty**: Easy

---

## Current State ✅

### What's Already Built:

1. ✅ **VE Heatmap Component** (`frontend/src/components/results/VEHeatmap.tsx`)
   - Fully functional 2D heatmap with color-coded cells
   - Interactive tooltips on hover
   - Clamped value indicators (yellow triangles)
   - Click handlers for cell selection
   - Responsive design with scrolling for large tables
   - Accessibility features (ARIA labels, keyboard navigation)

2. ✅ **VE Heatmap Legend** (`frontend/src/components/results/VEHeatmapLegend.tsx`)
   - Color scale legend
   - Shows clamp limit indicators

3. ✅ **Backend API Endpoint** (`/api/ve-data/<run_id>`)
   - Parses `VE_Correction_Delta_DYNO.csv` from run output
   - Returns correction data in proper format
   - Includes RPM and Load axis labels

4. ✅ **Frontend API Client** (`lib/analysis-api.ts`)
   - `fetchVEData(runId)` function exists
   - Proper TypeScript types defined

5. ✅ **Demo Page** (`pages/VEHeatmapDemo.tsx`)
   - Working example with sample data
   - Can be used as reference

### What's Missing:

1. ❌ Integration in `RunDetailPage.tsx` - Currently shows "coming soon" placeholder
2. ❌ React Query hook for fetching VE data from Jetstream runs
3. ❌ Parse VE correction CSV from stub data outputs

---

## Implementation Steps

### Step 1: Create React Query Hook for VE Data

**File**: `frontend/src/api/jetstream.ts` (or create `frontend/src/hooks/useVEData.ts`)

```typescript
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface VEData {
  rpm: number[];
  load: number[];
  corrections: number[][];
}

export function useVEData(runId: string | undefined) {
  return useQuery({
    queryKey: ['ve-data', runId],
    queryFn: async () => {
      if (!runId) throw new Error('Run ID is required');
      const response = await api.get(`/api/ve-data/${runId}`);
      return response.data as VEData;
    },
    enabled: !!runId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
```

### Step 2: Update RunDetailPage to Use VE Heatmap

**File**: `frontend/src/pages/RunDetailPage.tsx`

**Add imports** (around line 1-20):
```typescript
import { VEHeatmap } from '@/components/results/VEHeatmap';
import { VEHeatmapLegend } from '@/components/results/VEHeatmapLegend';
import { useVEData } from '@/api/jetstream'; // or '@/hooks/useVEData'
```

**Replace the placeholder section** (lines 314-327) with:
```typescript
<Card>
  <CardHeader>
    <CardTitle className="flex items-center gap-2">
      <Gauge className="h-5 w-5" />
      VE Heatmap
    </CardTitle>
    <CardDescription>Volumetric Efficiency corrections</CardDescription>
  </CardHeader>
  <CardContent>
    <VEHeatmapWithData runId={run.run_id} />
  </CardContent>
</Card>
```

**Add new component** (at the bottom of the file, before the export):
```typescript
function VEHeatmapWithData({ runId }: { runId: string }) {
  const { data: veData, isLoading, error } = useVEData(runId);

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="text-sm text-muted-foreground">Loading VE data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-64 bg-muted/50 rounded-lg flex items-center justify-center">
        <p className="text-muted-foreground">
          Unable to load VE data: {error instanceof Error ? error.message : 'Unknown error'}
        </p>
      </div>
    );
  }

  if (!veData || !veData.corrections || veData.corrections.length === 0) {
    return (
      <div className="h-64 bg-muted/50 rounded-lg flex items-center justify-center">
        <p className="text-muted-foreground">No VE correction data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <VEHeatmapLegend clampLimit={7} />
      <VEHeatmap
        data={veData.corrections}
        rowLabels={veData.rpm.map(String)}
        colLabels={veData.load.map(String)}
        clampLimit={7}
        showClampIndicators={true}
        showValues={true}
      />
    </div>
  );
}
```

### Step 3: Update Backend to Support Jetstream Runs

The backend endpoint `/api/ve-data/<run_id>` currently looks in `outputs/<run_id>/`. For Jetstream runs, we need to look in the run manager's directory structure.

**File**: `api/app.py`

**Update the `get_ve_data` function** (around line 374):

```python
@app.route("/api/ve-data/<run_id>", methods=["GET"])
def get_ve_data(run_id):
    """
    Get VE table data for 3D visualization

    Args:
        run_id: Unique run identifier

    Returns:
        JSON with VE data in format expected by frontend
    """
    try:
        run_id = secure_filename(run_id)
        
        # Try Jetstream run manager first
        try:
            from services.run_manager import get_run_manager
            manager = get_run_manager()
            run_output_dir = manager.get_run_output_dir(run_id)
            if run_output_dir and run_output_dir.exists():
                ve_delta_file = run_output_dir / "VE_Correction_Delta_DYNO.csv"
            else:
                # Fall back to old outputs folder
                output_dir = OUTPUT_FOLDER / run_id
                ve_delta_file = output_dir / "VE_Correction_Delta_DYNO.csv"
        except:
            # Fall back to old outputs folder
            output_dir = OUTPUT_FOLDER / run_id
            ve_delta_file = output_dir / "VE_Correction_Delta_DYNO.csv"

        if not ve_delta_file.exists():
            return jsonify({"error": "VE data not found"}), 404

        # Parse VE delta CSV
        import csv

        with open(ve_delta_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)

            # Extract kPa bins from header (skip first "RPM" column)
            load_points = [int(h) for h in header[1:]]

            rpm_points = []
            corrections = []

            for row in reader:
                rpm_points.append(int(row[0]))
                # Remove '+' prefix and convert to float
                corrections.append(
                    [float(val.replace("+", "").replace("'", "")) for val in row[1:]]
                )

        return (
            jsonify(
                {
                    "rpm": rpm_points,
                    "load": load_points,
                    "corrections": corrections,  # Changed from "before"/"after" to just corrections
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

---

## Testing Steps

### 1. Test with Stub Data

With stub mode enabled:

```powershell
# Backend
cd C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3
$env:JETSTREAM_STUB_DATA="true"
py -3.11 -m flask run --port 5100

# Frontend
cd frontend
$env:VITE_API_BASE_URL='http://127.0.0.1:5100'
npm run dev
```

1. Navigate to http://localhost:5001/jetstream
2. Click on the **Complete** run (`run_jetstream_demo_complete`)
3. Scroll down to the **VE Heatmap** section
4. Verify:
   - ✅ Heatmap loads and displays
   - ✅ Color gradient shows (green = small corrections, red/blue = large corrections)
   - ✅ Yellow triangles appear on clamped cells
   - ✅ Hover over cells shows tooltip with RPM, Load, and Correction value
   - ✅ Legend displays at the top

### 2. Test API Endpoint Directly

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5100/api/ve-data/run_jetstream_demo_complete" | ConvertTo-Json -Depth 5
```

Expected response:
```json
{
  "rpm": [1000, 1500, 2000, 2500, 3000, 3500, 4000],
  "load": [0, 10, 20, 30, 40, 50, 60, 70, 80, 100],
  "corrections": [
    [-2.5, -1.8, -0.3, 0.5, 1.2, 2.8, 4.5, 6.2, 8.1, 10.5],
    [-3.2, -2.1, -0.8, 0.2, 0.8, 2.1, 3.8, 5.5, 7.8, 9.2],
    ...
  ]
}
```

### 3. Test Error States

- Navigate to the **Error** run - should show "No VE correction data available"
- Navigate to the **Processing** run - should show "No VE correction data available"

---

## Expected Result

### Before:
```
┌─────────────────────────────────┐
│ VE Heatmap                      │
│ Volumetric Efficiency corrections│
├─────────────────────────────────┤
│                                 │
│  VE Heatmap visualization       │
│  coming soon                    │
│                                 │
└─────────────────────────────────┘
```

### After:
```
┌─────────────────────────────────┐
│ VE Heatmap                      │
│ Volumetric Efficiency corrections│
├─────────────────────────────────┤
│ [Legend: -7% ←→ +7%]           │
│                                 │
│      0  10  20  30  40  50 ... │
│ 1000 🟢 🟢 🟢 🟡 🟡 🟠 ...     │
│ 1500 🟢 🟢 🟢 🟡 🟠 🟠 ...     │
│ 2000 🔵 🟢 🟢 🟡 🟡 🟠 ...     │
│ 3000 🔵 🔵 🟢 🟢 🟡 🟠 ...     │
│ ...                             │
│                                 │
│ (Interactive, hover for details)│
└─────────────────────────────────┘
```

---

## Troubleshooting

### Issue: "VE data not found"
**Solution**: Check that the run has completed and has a `VE_Correction_Delta_DYNO.csv` file in its output directory.

### Issue: Heatmap shows but no colors
**Solution**: Verify the correction values are being parsed correctly. Check browser console for errors.

### Issue: API returns 500 error
**Solution**: Check backend logs for Python exceptions. Likely a CSV parsing issue.

### Issue: Heatmap is too large/small
**Solution**: The component has built-in scrolling. Adjust cell size in `VEHeatmap.tsx` if needed (currently `w-8 h-8`).

---

## File Checklist

Files to modify:
- [ ] `frontend/src/api/jetstream.ts` or `frontend/src/hooks/useVEData.ts` (create hook)
- [ ] `frontend/src/pages/RunDetailPage.tsx` (integrate heatmap)
- [ ] `api/app.py` (update endpoint to support Jetstream runs)

Files that already exist (no changes needed):
- ✅ `frontend/src/components/results/VEHeatmap.tsx`
- ✅ `frontend/src/components/results/VEHeatmapLegend.tsx`
- ✅ `frontend/src/lib/colorScale.ts`
- ✅ `api/jetstream/stub_data.py` (VE sample data already included)

---

## Bonus: Add to Other Pages

Once working in `RunDetailPage`, you can also add it to:

1. **Dashboard** (`pages/Dashboard.tsx`) - Show recent VE corrections
2. **History** (`pages/History.tsx`) - Compare VE corrections across runs
3. **VE Heatmap Demo** (`pages/VEHeatmapDemo.tsx`) - Already has examples

---

## Summary

**What you need to do:**

1. Create `useVEData` hook (5 minutes)
2. Update `RunDetailPage.tsx` to use the heatmap component (15 minutes)
3. Update backend `get_ve_data` to support Jetstream runs (10 minutes)
4. Test with stub data (10 minutes)

**Total time**: ~40 minutes

**Result**: Beautiful, interactive VE heatmap showing correction values with color coding, tooltips, and clamp indicators! 🎨📊

---

**Next Steps After VE Heatmap:**
- Implement Apply/Rollback controls
- Add real-time progress updates
- Add VE comparison view (before/after side-by-side)

