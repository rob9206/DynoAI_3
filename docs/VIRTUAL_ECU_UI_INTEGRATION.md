# Virtual ECU UI Integration Guide

**How to add Virtual ECU controls to the JetDrive Auto-Tune page**

---

## Overview

The Virtual ECU Panel provides UI controls for configuring realistic tuning scenarios in the simulator. Users can:
- Enable/disable Virtual ECU mode
- Select pre-configured scenarios (Perfect, Lean, Rich, Custom)
- Adjust VE error parameters
- Configure cylinder balance and environmental conditions

---

## Quick Integration

### Step 1: Add State Management

In `JetDriveAutoTunePage.tsx`, add state for Virtual ECU configuration:

```typescript
// Add to existing state declarations
const [virtualECUEnabled, setVirtualECUEnabled] = useState(false);
const [veScenario, setVeScenario] = useState<'perfect' | 'lean' | 'rich' | 'custom'>('lean');
const [veErrorPct, setVeErrorPct] = useState(-10.0);
const [veErrorStd, setVeErrorStd] = useState(5.0);
```

### Step 2: Import the Component

```typescript
import { VirtualECUPanel } from '../components/jetdrive/VirtualECUPanel';
```

### Step 3: Update Simulator Start Request

Modify the `startSimulator` mutation to include Virtual ECU config:

```typescript
const startSimulator = useMutation({
  mutationFn: async (profile: string) => {
    const res = await fetch(`${API_BASE}/simulator/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile,
        auto_pull: false,
        virtual_ecu: virtualECUEnabled ? {
          enabled: true,
          scenario: veScenario,
          ve_error_pct: veErrorPct,
          ve_error_std: veErrorStd,
          cylinder_balance: 'same',
          barometric_pressure_inhg: 29.92,
          ambient_temp_f: 75.0,
        } : { enabled: false },
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  onSuccess: () => {
    toast.success('Simulator started' + (virtualECUEnabled ? ' with Virtual ECU' : ''));
    queryClient.invalidateQueries({ queryKey: ['simulator-status'] });
  },
});
```

### Step 4: Add Panel to UI

Place the VirtualECUPanel in your layout (e.g., in a settings sheet or sidebar):

```typescript
<VirtualECUPanel
  enabled={virtualECUEnabled}
  onEnabledChange={setVirtualECUEnabled}
  scenario={veScenario}
  onScenarioChange={setVeScenario}
  veErrorPct={veErrorPct}
  onVeErrorChange={setVeErrorPct}
  veErrorStd={veErrorStd}
  onVeErrorStdChange={setVeErrorStd}
/>
```

---

## Complete Example

Here's a complete integration example:

```typescript
// In JetDriveAutoTunePage.tsx

import { VirtualECUPanel, VEScenario } from '../components/jetdrive/VirtualECUPanel';

export function JetDriveAutoTunePage() {
  // ... existing state ...

  // Virtual ECU state
  const [virtualECUEnabled, setVirtualECUEnabled] = useState(false);
  const [veScenario, setVeScenario] = useState<VEScenario>('lean');
  const [veErrorPct, setVeErrorPct] = useState(-10.0);
  const [veErrorStd, setVeErrorStd] = useState(5.0);

  // Update simulator start mutation
  const startSimulator = useMutation({
    mutationFn: async (profile: string) => {
      const res = await fetch(`${API_BASE}/simulator/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile,
          auto_pull: false,
          virtual_ecu: virtualECUEnabled ? {
            enabled: true,
            scenario: veScenario,
            ve_error_pct: veErrorPct,
            ve_error_std: veErrorStd,
            cylinder_balance: 'same',
            barometric_pressure_inhg: 29.92,
            ambient_temp_f: 75.0,
          } : { enabled: false },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: (data) => {
      const ecuStatus = data.virtual_ecu_enabled ? ' with Virtual ECU' : '';
      toast.success(`Simulator started${ecuStatus}`);
      queryClient.invalidateQueries({ queryKey: ['simulator-status'] });
    },
  });

  return (
    <div className="space-y-6">
      {/* ... existing content ... */}

      {/* Add Virtual ECU Panel in a settings sheet or sidebar */}
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="outline">
            <Settings2 className="h-4 w-4 mr-2" />
            Virtual ECU Settings
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-[400px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Virtual ECU Configuration</SheetTitle>
            <SheetDescription>
              Configure realistic tuning scenarios for testing
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6">
            <VirtualECUPanel
              enabled={virtualECUEnabled}
              onEnabledChange={setVirtualECUEnabled}
              scenario={veScenario}
              onScenarioChange={setVeScenario}
              veErrorPct={veErrorPct}
              onVeErrorChange={setVeErrorPct}
              veErrorStd={veErrorStd}
              onVeErrorStdChange={setVeErrorStd}
            />
          </div>
        </SheetContent>
      </Sheet>

      {/* ... rest of your page ... */}
    </div>
  );
}
```

---

## API Integration

### Backend Endpoint

The `/simulator/start` endpoint now accepts Virtual ECU configuration:

```python
POST /api/jetdrive/simulator/start
Content-Type: application/json

{
  "profile": "m8_114",
  "auto_pull": false,
  "virtual_ecu": {
    "enabled": true,
    "scenario": "lean",           // "perfect" | "lean" | "rich" | "custom"
    "ve_error_pct": -10.0,        // For custom scenario
    "ve_error_std": 5.0,          // For custom scenario
    "cylinder_balance": "same",   // "same" | "front_rich" | "rear_rich"
    "barometric_pressure_inhg": 29.92,
    "ambient_temp_f": 75.0
  }
}
```

### Response

```json
{
  "success": true,
  "virtual_ecu_enabled": true,
  "profile": "m8_114",
  "state": "idle"
}
```

---

## User Experience Flow

### 1. Enable Virtual ECU

User toggles the Virtual ECU switch → Panel expands with configuration options

### 2. Select Scenario

User selects from dropdown:
- **Perfect**: VE table matches engine (AFR on target)
- **Lean**: VE 10% too low (typical untuned engine)
- **Rich**: VE 10% too high
- **Custom**: User-defined VE error

### 3. Start Simulator

User clicks "Start Simulator" → Backend creates Virtual ECU with selected configuration

### 4. Run Pull

User triggers dyno pull → AFR errors appear based on VE table mismatches

### 5. Analyze Results

User clicks "Analyze" → AutoTune workflow calculates VE corrections

### 6. Compare

User can see:
- AFR errors correlate with VE table inaccuracy
- Corrections needed match the intentional error
- Realistic tuning scenario

---

## Visual Indicators

Add visual feedback to show Virtual ECU is active:

```typescript
{virtualECUEnabled && (
  <Alert className="bg-purple-500/10 border-purple-500/30">
    <Cpu className="h-4 w-4 text-purple-500" />
    <AlertDescription>
      Virtual ECU Active: <strong>{veScenario}</strong> scenario
      {veScenario === 'custom' && ` (${veErrorPct > 0 ? '+' : ''}${veErrorPct}% VE error)`}
    </AlertDescription>
  </Alert>
)}
```

---

## Testing Workflow

### Test Case 1: Perfect VE

1. Enable Virtual ECU
2. Select "Perfect VE" scenario
3. Start simulator and run pull
4. Analyze results
5. **Expected**: AFR on target (±0.05), no corrections needed

### Test Case 2: Lean Condition

1. Enable Virtual ECU
2. Select "Lean (VE -10%)" scenario
3. Start simulator and run pull
4. Analyze results
5. **Expected**: AFR 1-1.5 points lean, +10% VE correction needed

### Test Case 3: Custom Error

1. Enable Virtual ECU
2. Select "Custom" scenario
3. Set VE error to -15%
4. Start simulator and run pull
5. Analyze results
6. **Expected**: AFR ~1.8 points lean, +15% VE correction needed

---

## Advanced Features

### Cylinder Balance

```typescript
<Select defaultValue="same">
  <SelectItem value="same">Same VE (Front/Rear)</SelectItem>
  <SelectItem value="front_rich">Front 5% Richer</SelectItem>
  <SelectItem value="rear_rich">Rear 5% Richer</SelectItem>
</Select>
```

This simulates V-twin cylinder imbalance (common in real engines).

### Environmental Conditions

```typescript
<Select defaultValue="sealevel">
  <SelectItem value="sealevel">Sea Level (29.92 inHg)</SelectItem>
  <SelectItem value="altitude">5000 ft (24.9 inHg)</SelectItem>
  <SelectItem value="hot">Hot Day (95°F)</SelectItem>
</Select>
```

This affects air density calculations in the Virtual ECU.

---

## Troubleshooting

### Virtual ECU not affecting AFR

**Check:**
- Is Virtual ECU enabled in the panel?
- Did you restart the simulator after changing settings?
- Check browser console for errors

### AFR errors seem wrong

**Check:**
- Verify VE error percentage is correct
- Check scenario selection (Perfect vs Lean vs Rich)
- Review backend logs for Virtual ECU creation

### Simulator won't start

**Check:**
- Backend logs for errors
- Ensure `api/services/virtual_ecu.py` is accessible
- Verify numpy/scipy are installed

---

## Benefits

### For Users

- **Visual Configuration**: No code needed to test tuning scenarios
- **Instant Feedback**: See AFR errors in real-time
- **Educational**: Learn how VE errors manifest as AFR errors
- **Safe Testing**: No risk to real engines

### For Developers

- **Reusable Component**: VirtualECUPanel can be used anywhere
- **Type-Safe**: Full TypeScript support
- **Extensible**: Easy to add new scenarios
- **Well-Documented**: Clear API and examples

---

## Next Steps

### Phase 3: Closed-Loop Orchestrator UI

Add UI for multi-iteration tuning:

```typescript
<ClosedLoopTuningPanel
  enabled={closedLoopEnabled}
  maxIterations={10}
  convergenceThreshold={0.3}
  onIterationComplete={(iteration, results) => {
    // Update UI with progress
  }}
/>
```

This will enable fully automated tuning simulation from the UI!

---

## Resources

- **Component**: `frontend/src/components/jetdrive/VirtualECUPanel.tsx`
- **Backend**: `api/routes/jetdrive.py` (simulator/start endpoint)
- **Core Logic**: `api/services/virtual_ecu.py`
- **Documentation**: `docs/VIRTUAL_ECU_SIMULATION.md`
- **Quick Start**: `QUICK_START_VIRTUAL_ECU.md`

---

## Summary

✅ **UI Component Created**: VirtualECUPanel with full configuration options  
✅ **Backend Integration**: `/simulator/start` endpoint supports Virtual ECU  
✅ **Type-Safe**: Full TypeScript support  
✅ **User-Friendly**: Pre-configured scenarios + custom options  
✅ **Extensible**: Easy to add new features  

**Ready to integrate into your Auto-Tune page!** 🚀

