# 🚀 DynoAI Quick Start Guide

## What is DynoAI?

DynoAI is a modern web application that analyzes dyno tuning logs and generates VE corrections, spark timing suggestions, and comprehensive diagnostics. Upload your CSV file and get instant results!

---

## ⚡ 3-Step Quick Start

### Step 1: Start the Application

**Linux/Mac:**
```bash
cd /vercel/sandbox
./start-dev.sh
```

**Windows:**
```cmd
cd \vercel\sandbox
start-dev.bat
```

### Step 2: Open Your Browser

Navigate to: **http://localhost:5173**

### Step 3: Upload & Analyze

1. Drag & drop your CSV file (or click to browse)
2. Click "Start Analysis"
3. Wait for results (30-60 seconds)
4. Download your corrections!

---

## 📋 What You Need

- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **Your dyno log** - WinPEP, PowerVision, or generic CSV format

---

## 🎯 What You Get

After analysis, you'll receive:

### VE Corrections
- ✅ Percentage corrections for each RPM/MAP cell
- ✅ Paste-ready format for your ECU software
- ✅ Updated VE tables (if you provide base tables)

### Spark Timing
- ✅ Front and rear cylinder suggestions
- ✅ Knock-aware recommendations
- ✅ Temperature-compensated adjustments

### Diagnostics
- ✅ AFR error maps
- ✅ Data coverage analysis
- ✅ Anomaly detection
- ✅ Quality metrics

---

## 🖥️ User Interface

### Dashboard (Upload Page)
```
┌─────────────────────────────────────────┐
│  DynoAI                    Dashboard    │
├─────────────────────────────────────────┤
│                                         │
│      Welcome to DynoAI                  │
│   Upload your dyno log to generate     │
│        VE corrections                   │
│                                         │
│  ┌───────────────────────────────┐    │
│  │                                │    │
│  │   📁 Drop CSV file here        │    │
│  │      or click to browse        │    │
│  │                                │    │
│  └───────────────────────────────┘    │
│                                         │
│      [Start Analysis]                   │
│                                         │
└─────────────────────────────────────────┘
```

### Results Page
```
┌─────────────────────────────────────────┐
│  ← Back              [Download All]     │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │
│  │1,234│ │ 156 │ │2.5% │ │7.0% │      │
│  │Rows │ │Fixes│ │ Avg │ │ Max │      │
│  └─────┘ └─────┘ └─────┘ └─────┘      │
│                                         │
│  Output Files:                          │
│  📊 VE_Correction_Delta.csv [Download]  │
│  📊 Spark_Suggestions.csv   [Download]  │
│  📄 Diagnostics_Report.txt  [Download]  │
│                                         │
└─────────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### "Port already in use"
```bash
# Kill the process
lsof -ti:5001 | xargs kill -9  # Backend
lsof -ti:5173 | xargs kill -9  # Frontend
```

### "Module not found"
```bash
# Reinstall dependencies
pip install -r requirements.txt
cd frontend && npm install
```

### "Can't connect to API"
1. Check backend is running on port 5001
2. Check frontend is running on port 5173
3. Restart both servers

---

## 📚 More Information

- **Full User Guide**: See `WEB_APP_README.md`
- **Deployment Guide**: See `DEPLOYMENT_GUIDE.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`

---

## 🎓 Tips

### For Best Results
- ✅ Use steady-state dyno pulls
- ✅ Ensure good data coverage across RPM/MAP range
- ✅ Check for sensor errors before uploading
- ✅ Review diagnostics for anomalies

### File Requirements
- **Format**: CSV or TXT
- **Size**: Up to 50MB
- **Types**: WinPEP, PowerVision, Generic
- **Columns**: Must include RPM, MAP, Torque, AFR

---

## 🆘 Need Help?

1. Check the troubleshooting section above
2. Review the full documentation in `WEB_APP_README.md`
3. Check browser console for errors (F12)
4. Check backend logs at `/tmp/dynoai_backend.log`

---

## 🎉 That's It!

You're ready to start tuning with AI assistance!

```bash
./start-dev.sh  # Start the app
```

Then open **http://localhost:5173** and upload your first log!

**Happy Tuning! 🏁**
