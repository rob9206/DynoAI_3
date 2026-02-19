# Phase 6: Auto-Mapping Improvements - COMPLETE

## Summary

Successfully enhanced JetDrive auto-mapping with JDUnit-based inference, confidence scoring, and import/export capabilities to reduce manual PowerCore configuration churn.

## Implementation Details

### 1. Enhanced Auto-Mapping Engine (`api/services/jetdrive_mapping.py`)

**New Data Class:**
- `MappingConfidence`: Dataclass with confidence score (0.0-1.0), reasons list, warnings list, and recommended transform

**Unit-Based Inference:**

Added `CANONICAL_UNIT_TYPES` mapping from canonical names to JDUnit enum values:
- `rpm` → JDUnit.EngineSpeed (8)
- `afr_*` → JDUnit.AFR (11)
- `lambda_*` → JDUnit.Lambda (13) with auto-transform
- `map_kpa` → JDUnit.Pressure (7)
- `tps` → JDUnit.Percentage (16)
- `torque` → JDUnit.Torque (5)
- `power` → JDUnit.Power (4)
- `ect/iat` → JDUnit.Temperature (6)

**Confidence Scoring Algorithm:**

`score_channel_for_canonical()` assigns scores based on:
- **Unit match (+0.5)**: Channel unit matches expected JDUnit for canonical name
- **Name pattern match (+0.3)**: Channel name contains expected pattern
- **Disambiguation bonus (+0.2)**: No other channel has higher score

**New Functions:**
- `score_channel_for_canonical(channel, canonical_name, all_channels)` - Score a single channel
- `auto_map_channels_with_confidence(provider)` - Auto-detect with confidence tracking
- `get_unmapped_required_channels(mapping)` - Find missing required channels
- `get_low_confidence_mappings(confidence_map, threshold)` - Find low-confidence mappings

**Backward Compatibility:**
- Original `auto_map_channels()` now wraps the new confidence-based function
- Existing API endpoints continue to work unchanged

### 2. Confidence Report API (`api/routes/jetdrive.py`)

**New Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mapping/confidence` | GET | Get confidence report with readiness status |
| `/mapping/export/<signature>` | GET | Export mapping as downloadable JSON |
| `/mapping/import` | POST | Import mapping from JSON file |
| `/mapping/export-template` | POST | Export current mapping as reusable template |

**Confidence Report Response:**

```json
{
  "success": true,
  "provider_signature": "4097_192.168.1.50_a1b2c3d4",
  "overall_confidence": 0.85,
  "ready_for_capture": true,
  "mappings": [
    {
      "canonical_name": "rpm",
      "source_id": 10,
      "source_name": "Digital RPM 1",
      "confidence": 0.95,
      "reasons": ["Unit match (EngineSpeed)", "Name pattern match", "Best match among available channels"],
      "warnings": [],
      "transform": "identity"
    }
  ],
  "unmapped_required": [],
  "unmapped_recommended": ["map_kpa", "tps"],
  "low_confidence": [],
  "has_existing_mapping": true
}
```

**Readiness Logic:**
```python
ready_for_capture = (
    len(unmapped_required) == 0 and
    overall_confidence >= 0.7 and
    len(low_confidence) == 0
)
```

### 3. Frontend: Mapping Confidence Panel (`frontend/src/components/jetdrive/MappingConfidencePanel.tsx`)

**Features:**
- Overall confidence score with progress bar (color-coded: green >80%, yellow 50-80%, red <50%)
- Readiness indicator (green "Ready for Capture" or yellow "Review Required")
- Per-channel confidence display with tooltips showing reasons and warnings
- Missing required channels alert (red)
- Low-confidence warnings alert (yellow)
- Unmapped recommended channels info (blue)
- Import/Export buttons with file picker
- Refresh button to re-check confidence

**Visual Hierarchy:**
1. Readiness indicator (most prominent)
2. Overall confidence bar
3. Missing required channels (if any)
4. Channel list with individual confidence badges
5. Low-confidence warnings
6. Unmapped recommended info
7. Import/Export controls

### 4. Pre-Capture Warning Integration (`frontend/src/components/jetdrive/JetDriveLiveDashboard.tsx`)

**Changes:**
- Added `mappingReady` state tracked by confidence panel callback
- Added `showConfidenceWarning` dialog state
- Modified `handleToggleCapture()` to check `mappingReady` before starting
- Added `AlertDialog` component with:
  - Warning title with AlertTriangle icon
  - Explanation of risks (incorrect data, missing signals)
  - Recommended actions list
  - "Cancel" button to abort capture
  - "Proceed Anyway" button (yellow) to override

**Flow:**
1. User clicks "Start Capture"
2. If `!mappingReady`, show warning dialog
3. User can cancel (returns to dashboard) or proceed anyway
4. If proceeding, capture starts as normal

### 5. Hardware Tab Integration (`frontend/src/components/jetdrive/HardwareTab.tsx`)

**Added:**
- `MappingConfidencePanel` import
- Rendered immediately after `PreflightCheckPanel` for visibility
- Provides pre-capture readiness check before user goes to Live tab

### 6. Tests (`tests/api/test_jetdrive_mapping_confidence.py`)

**24 tests covering:**

1. **Unit Inference (6 tests)**
   - RPM, AFR, Lambda, Pressure, Percentage, Torque/Power unit detection
   - Transform auto-detection for Lambda → AFR

2. **Confidence Scoring (5 tests)**
   - High confidence (unit + name match)
   - Medium confidence (name only)
   - Low confidence (no match)
   - Disambiguation bonus
   - Warning generation

3. **Auto-Mapping (4 tests)**
   - All channels detection
   - High-confidence preference
   - No duplicate source channels
   - Threshold enforcement

4. **Mapping Validation (4 tests)**
   - Missing RPM detection
   - Missing AFR detection
   - All required present validation
   - Low-confidence detection

5. **Import/Export (4 tests)**
   - Export format validation
   - Import valid mapping
   - Import invalid format rejection
   - Template export

6. **Persistence (1 test)**
   - Save and load round-trip

**All tests pass in 0.32s.**

## Export/Import Format

**Export Format:**
```json
{
  "version": "1.0",
  "type": "dynoai_mapping_export",
  "name": "Test Dyno Mapping",
  "description": "Channel mapping for Test Dyno (ID: 0x1001)",
  "created_at": "2026-01-28T00:00:00",
  "exported_at": "2026-01-28T05:00:00",
  "provider_signature": "4097_192.168.1.50_a1b2c3d4",
  "provider_id": 4097,
  "provider_name": "Test Dyno",
  "host": "192.168.1.50",
  "channels": {
    "rpm": {
      "source_id": 10,
      "source_name": "Digital RPM 1",
      "transform": "identity",
      "enabled": true
    }
  }
}
```

**Template Format:**
```json
{
  "version": "1.0",
  "type": "dynoai_mapping_template",
  "name": "My Shop Template",
  "description": "Custom template for shop dyno",
  "created_at": "2026-01-28T00:00:00",
  "channels": {
    "rpm": {"source_id": 10, "source_name": "Digital RPM 1", "transform": "identity"}
  }
}
```

## Acceptance Criteria Met

### 1. First-time Setup Creates Mapping Once ✅

- Auto-detect now uses unit inference (JDUnit enum) + name patterns + confidence scoring
- Mappings saved to `config/jetdrive_mappings/<signature>.json`
- Subsequent sessions auto-load from file (existing behavior preserved)
- Confidence threshold (0.5) ensures only reasonable matches are accepted

### 2. UI Shows "What's Missing" Before Capture ✅

- `MappingConfidencePanel` displays missing required channels in red alert
- Clear list: "rpm", "afr (any)"
- Fix suggestions: "Enable these channels in Power Core JetDrive settings"
- Visible in Hardware tab before user navigates to Live tab

### 3. UI Shows "What Looks Mislabeled" ✅

- Low-confidence mappings (<70%) shown in yellow alert
- Per-channel confidence badges (color-coded)
- Tooltips with reasons and warnings
- Pre-capture warning dialog if `!mappingReady`
- Dialog blocks capture start unless user explicitly proceeds

### 4. Import/Export Works ✅

- Export downloads JSON file with full mapping data
- Import accepts JSON file via file picker
- Export as template saves to `config/jetdrive_mappings/template_*.json`
- Templates appear in template list for future use

## Usage Examples

### Backend API

**Get Confidence Report:**
```bash
curl "http://localhost:5001/api/jetdrive/mapping/confidence"
```

**Export Mapping:**
```bash
curl "http://localhost:5001/api/jetdrive/mapping/export/4097_192.168.1.50_a1b2c3d4" -o mapping.json
```

**Import Mapping:**
```bash
curl -X POST "http://localhost:5001/api/jetdrive/mapping/import" \
  -F "file=@mapping.json"
```

**Export as Template:**
```bash
curl -X POST "http://localhost:5001/api/jetdrive/mapping/export-template" \
  -H "Content-Type: application/json" \
  -d '{"signature": "4097_192.168.1.50_a1b2c3d4", "template_name": "My Shop", "description": "Custom setup"}'
```

### Frontend Workflow

1. Navigate to Hardware tab
2. See `MappingConfidencePanel` showing overall readiness
3. If not ready (red/yellow), click "Auto-Detect" in Channel Mapping panel
4. Review confidence scores and warnings
5. Save mapping
6. Export mapping for backup or sharing
7. Navigate to Live tab
8. Click "Start Capture" - no warning if ready, dialog if not ready

## Files Created/Modified

### Modified Files:
- `api/services/jetdrive_mapping.py` - Added confidence scoring, unit inference, import/export helpers
- `api/routes/jetdrive.py` - Added 4 new endpoints (confidence, export, import, export-template)
- `frontend/src/components/jetdrive/ChannelMappingPanel.tsx` - Updated success message
- `frontend/src/components/jetdrive/JetDriveLiveDashboard.tsx` - Added pre-capture warning dialog
- `frontend/src/components/jetdrive/HardwareTab.tsx` - Added MappingConfidencePanel

### New Files:
- `frontend/src/components/jetdrive/MappingConfidencePanel.tsx` - Confidence panel UI
- `tests/api/test_jetdrive_mapping_confidence.py` - 24 tests, all passing

## Benefits

### Before Phase 6:
- Manual pattern matching only (no unit awareness)
- No confidence feedback
- Trial and error to find correct channels
- Repeated setup for same dyno
- No import/export capability

### After Phase 6:
- Unit-aware inference using JDUnit enum
- Confidence scores with reasons and warnings
- Clear pre-capture readiness check
- One-time setup per dyno/provider
- Import/export for backup and sharing
- Reduced PowerCore enablement churn

## Performance

- Confidence scoring is O(n × m) where n = provider channels, m = canonical channels
  - Typical: 20 channels × 14 canonical = 280 operations
  - Negligible overhead during auto-detect (runs once on demand)
- No impact on live capture (20Hz maintained)

## Next Steps (Remaining Phases)

Phase 6 is complete. Remaining phases from roadmap:
- **Phase 5**: Auto-run detection, session segmentation, replay (skipped ahead to Phase 6)
- **Phase 7**: Predictive test planning with coverage gap suggestions
