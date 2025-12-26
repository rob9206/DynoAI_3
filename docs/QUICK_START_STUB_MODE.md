# Quick Start: Jetstream Stub Mode

Run the DynoAI frontend with sample Jetstream data (no API key needed).

## One-Command Start

### Terminal 1 - Backend:
```powershell
cd C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3 && $env:PYTHONPATH="C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3;C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3\api"; $env:JETSTREAM_STUB_DATA="true"; $env:JETSTREAM_ENABLED="false"; $env:FLASK_APP="api.app"; py -3.11 -m flask run --port 5100
```

### Terminal 2 - Frontend:
```powershell
cd C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3\frontend && $env:VITE_API_BASE_URL='http://127.0.0.1:5100'; npm run dev
```

## Access

- **Frontend**: http://localhost:5001 (or whatever port Vite assigns)
- **Backend API**: http://127.0.0.1:5100/api

## Sample Data

You'll see 3 Jetstream runs:
1. ✅ **Complete** - 2021 FXLRST with VE corrections
2. ⏳ **Processing** - 2019 Road Glide at 62%
3. ❌ **Error** - 2020 Softail with CSV error

## Test API Directly

```powershell
# List runs
Invoke-RestMethod http://127.0.0.1:5100/api/jetstream/runs | ConvertTo-Json -Depth 5

# Get status
Invoke-RestMethod http://127.0.0.1:5100/api/jetstream/status | ConvertTo-Json

# Trigger sync
Invoke-RestMethod -Method POST http://127.0.0.1:5100/api/jetstream/sync | ConvertTo-Json
```

## Switch to Real API

Change environment variables:
```powershell
$env:JETSTREAM_STUB_DATA="false"
$env:JETSTREAM_ENABLED="true"
$env:JETSTREAM_API_KEY="your-real-key"
$env:JETSTREAM_API_URL="https://api.jetstream.dynojet.com"
```

---

See `STUB_DATA_TESTING_SUMMARY.md` for full details.

