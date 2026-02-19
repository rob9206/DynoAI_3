# DynoAI Services Startup

## ✅ Services Started

I've launched both the backend and frontend servers in separate terminal windows.

### 🔧 Backend (Flask API)
- **URL**: http://localhost:5001
- **Process**: `python -m api.app`
- **Terminal**: Look for window titled "Administrator: cmd"
- **Health Check**: http://localhost:5001/api/health

### 🎨 Frontend (React + Vite)
- **URL**: http://localhost:5173
- **Process**: `npm run dev`
- **Terminal**: Look for window titled "Administrator: cmd"
- **Status**: Should show "Local: http://localhost:5173"

## 📝 What to Check

1. **Backend Terminal** should show:
   ```
   * Running on http://127.0.0.1:5001
   * Debug mode: on
   ```

2. **Frontend Terminal** should show:
   ```
   VITE v5.x.x  ready in xxx ms
   ➜  Local:   http://localhost:5173/
   ```

## 🧪 Test the Integration

Now you can test the PyQt6 GUI with live backend:

```powershell
cd C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3
python gui/main.py
```

### Test These Features:

1. **Dashboard Page**
   - Upload a log file
   - Start analysis
   - View results

2. **JetDrive Command Center**
   - Go to "JetDrive Live" in sidebar
   - Try the 3 tabs:
     - **Live Dashboard**: See gauges and VE table
     - **Hardware**: View dyno config, ingestion health, Innovate AFR
     - **AFR Targets**: Edit AFR values (try invalid input to see validation)

3. **Signal Integration** (with backend running):
   - Hardware tab panels will attempt API calls
   - Dyno Config will fetch from `/api/jetdrive/dyno/config`
   - Ingestion Health will poll `/api/jetdrive/ingestion/health`

## 🔄 If Services Didn't Start

If the terminals closed or services aren't running, you can manually start them:

### Manual Backend Start:
```powershell
cd C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3
python -m api.app
```

### Manual Frontend Start:
```powershell
cd C:\Users\dawso\OneDrive\Documents\GitHub\DynoAI_3\frontend
npm run dev
```

## 🛑 Stop Services

To stop the services:
1. Close the cmd terminal windows
2. Or press `Ctrl+C` in each terminal

## 🌐 Access Points

Once both are running:

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | http://localhost:5001 | REST API endpoints |
| API Docs | http://localhost:5001/docs | Swagger documentation |
| Health Check | http://localhost:5001/api/health | Service status |
| Frontend | http://localhost:5173 | React web interface |
| PyQt6 GUI | `python gui/main.py` | Desktop application |

## 🎯 Next Steps

1. ✅ Check that both terminal windows are open and showing startup messages
2. ✅ Visit http://localhost:5173 to see the React frontend
3. ✅ Visit http://localhost:5001/api/health to verify backend
4. ✅ Launch PyQt6 GUI: `python gui/main.py`
5. ✅ Test JetDrive features with live backend integration

