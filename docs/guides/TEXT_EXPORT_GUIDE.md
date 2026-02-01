# Text Export Feature for AI Analysis

## Overview

The DynoAI system now includes a comprehensive text export feature that allows you to export complete analysis results in a human-readable text format. This is particularly useful for:

- Sharing analysis results with AI assistants (ChatGPT, Claude, etc.)
- Creating reports for documentation
- Archiving analysis results in a portable format
- Reviewing analysis data without the web interface

## How to Use

### Via Web Interface

1. Navigate to the **JetDrive Auto-Tune** page
2. Run an analysis or select an existing run from the list
3. In the results tabs, click on the **Text Export** tab
4. Click the **Download .txt** button to save the comprehensive report

### Via API

You can also access the text export programmatically:

```bash
# Get text export for a specific run
curl http://localhost:5001/api/jetdrive/run/test_run/export-text

# Response will include:
{
  "run_id": "test_run",
  "filename": "DynoAI_Analysis_test_run.txt",
  "content": "... full text report ..."
}
```

## What's Included

The text export includes the following sections:

### 1. Run Information
- Run ID
- Timestamp
- Data source (simulation, Power Vision, JetDrive)

### 2. Performance Summary
- Peak Horsepower and RPM
- Peak Torque and RPM
- Total samples collected
- Test duration

### 3. AFR Analysis
- Overall status (LEAN, RICH, BALANCED)
- Zone distribution:
  - Lean cells (requiring fuel increase)
  - Rich cells (requiring fuel decrease)
  - OK cells (within tolerance)
  - No data cells (insufficient samples)

### 4. VE Correction Grid (2D)
- Complete RPM × MAP grid showing VE correction multipliers
- Format: CSV-compatible for easy parsing
- Shows corrections applied (e.g., 1.00 = no change, 1.05 = +5%, 0.95 = -5%)

### 5. AFR Error Grid (2D)
- AFR error in AFR points for each zone
- Positive values = lean (needs more fuel)
- Negative values = rich (needs less fuel)

### 6. Hit Count Grid (2D)
- Number of samples collected per zone
- Helps identify zones with sufficient data for reliable corrections

### 7. Diagnostics Report
- Detailed analysis results
- Recommendations and next steps
- VE correction strategy details

### 8. Grid Configuration
- RPM bins used for analysis
- MAP bins used for analysis
- Total grid size

## Example Output

```
================================================================================
DYNOAI AUTO-TUNE ANALYSIS REPORT
================================================================================

RUN INFORMATION
--------------------------------------------------------------------------------
Run ID: test_run
Timestamp: 2025-01-15T10:30:00Z
Data Source: simulation

PERFORMANCE SUMMARY
--------------------------------------------------------------------------------
Peak Horsepower: 95.50 HP @ 5200 RPM
Peak Torque: 102.30 lb-ft @ 3500 RPM
Total Samples: 1500
Duration: 45.0 seconds

AFR ANALYSIS
--------------------------------------------------------------------------------
Overall Status: BALANCED
Lean Cells: 12
Rich Cells: 8
OK Cells: 65
No Data Cells: 14

VE CORRECTION GRID (2D)
--------------------------------------------------------------------------------
Format: RPM | MAP bins (kPa)

RPM,30,40,50,60,70,80,90,100,110
1500,1.00,1.01,1.02,1.00,0.99,0.98,1.00,1.01,1.00
2000,1.01,1.02,1.03,1.01,0.98,0.97,0.99,1.02,1.01
...
```

## Use Cases with AI Assistants

### Example Prompts for ChatGPT

1. **General Analysis**:
   ```
   I have the following dyno analysis results. Can you review them and 
   provide recommendations for improvement?
   
   [paste text export here]
   ```

2. **Specific Questions**:
   ```
   Based on this VE correction data, which RPM/MAP zones need the most 
   attention? Should I focus on the lean or rich areas first?
   
   [paste text export here]
   ```

3. **Comparison**:
   ```
   I have two dyno runs - before and after corrections. Can you compare 
   them and tell me if the corrections improved the tune?
   
   Run 1 (before):
   [paste first export]
   
   Run 2 (after):
   [paste second export]
   ```

## Technical Details

- **Endpoint**: `/api/jetdrive/run/<run_id>/export-text`
- **Method**: GET
- **Response Format**: JSON with `content` field containing the full text report
- **File Extension**: `.txt`
- **Character Encoding**: UTF-8
- **Line Endings**: Unix-style (LF)

## File Naming Convention

Exported files follow this naming pattern:
```
DynoAI_Analysis_<run_id>.txt
```

For example:
- `DynoAI_Analysis_test_run.txt`
- `DynoAI_Analysis_run_1705315800.txt`

## Benefits

1. **Portability**: Plain text files can be opened anywhere
2. **AI-Friendly**: Structured format is easy for AI to parse and analyze
3. **Complete**: Includes all analysis data in one file
4. **Archival**: Simple format for long-term storage
5. **Shareable**: Easy to share via email, chat, or file sharing

## Related Documentation

- [JetDrive Auto-Tune Guide](JETDRIVE_HARDWARE_TESTING.md)
- [VE Operations Guide](README_VE_OPERATIONS.md)
- [API Documentation](README.md#api-endpoints)
