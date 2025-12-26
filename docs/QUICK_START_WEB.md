# 🚀 DynoAI Web Interface - Quick Reference

## Start Everything (One Command)

```powershell
.\start-web.ps1
```

Then open: **<http://localhost:5173>**

---

## Manual Startup

### Backend (Terminal 1)

```powershell
.venv\Scripts\Activate.ps1
python api\app.py
```

### Frontend (Terminal 2)

```powershell
cd frontend
npm run dev
```

---

## Testing

### Test API

```powershell
.\test-api.ps1
```

### Test Frontend

Open browser: **<http://localhost:5173>**

Upload test file: `archive\FXDLS_Wheelie_Spark_Delta-1.csv`

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/analyze` | POST | Upload & analyze CSV |
| `/api/download/{runId}/{file}` | GET | Download output |
| `/api/ve-data/{runId}` | GET | Get VE grid data |
| `/api/runs` | GET | List all runs |

---

## File Locations

```
api/app.py              # Flask API server
frontend/src/           # React components
uploads/                # Uploaded CSV files
outputs/                # Analysis results
```

---

## Configuration

### Backend

- **Port**: 5000
- **File size limit**: 16MB
- **Allowed types**: CSV only

### Frontend

- **Port**: 5173
- **API URL**: `VITE_API_URL` in `.env`
- **Mode**: Toggle `useRealAPI` in `AnalyzeRun.tsx`

---

## Workflow

1. 📁 Upload CSV file (drag-and-drop)
2. ▶️ Click "Run Analysis"
3. 📊 View manifest stats
4. 💾 Download output files
5. 🎨 Click "Visualize VE"
6. 🔮 View 3D surfaces
7. 🔄 Rotate and explore

---

## Troubleshooting

### Backend won't start

```powershell
.venv\Scripts\Activate.ps1
pip install -r api\requirements.txt
```

### Frontend won't start

```powershell
cd frontend
npm install
```

### "Connection refused"

- Check backend running: `http://localhost:5001/api/health`
- Check `VITE_API_URL` in `frontend/.env`

---

## Documentation

- **Setup Guide**: [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- **Summary**: [WEB_INTEGRATION_SUMMARY.md](WEB_INTEGRATION_SUMMARY.md)
- **Main Docs**: [README.md](README.md)

---

## Next Steps

1. ✅ Install dependencies: `pip install -r api/requirements.txt`
2. ✅ Install frontend: `cd frontend && npm install`
3. 🚀 Run: `.\start-web.ps1`
4. 🌐 Open: **<http://localhost:5173>**
5. 📤 Upload: Test CSV file
6. 🎉 Enjoy!
