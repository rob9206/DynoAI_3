#!/bin/bash

# DynoAI Development Startup Script
# Starts both backend (Flask) and frontend (Vite) servers

echo "======================================"
echo "[*] Starting DynoAI Development Servers"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}[!] Python 3 not found. Please install Python 3.8 or higher.${NC}"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}[!] Node.js not found. Please install Node.js 18 or higher.${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${BLUE}[>] Installing Python dependencies...${NC}"
pip install -q -r requirements.txt

# Install Node dependencies
echo -e "${BLUE}[>] Installing Node dependencies...${NC}"
cd frontend
npm install --silent
cd ..

echo ""
echo -e "${GREEN}[+] Dependencies installed${NC}"
echo ""

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}[*] Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Flask backend
echo -e "${BLUE}[>] Starting Flask backend on http://localhost:5001${NC}"
python3 api/app.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start Vite frontend
echo -e "${BLUE}[>] Starting Vite frontend on http://localhost:5173${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================"
echo -e "${GREEN}[+] DynoAI is running!${NC}"
echo "======================================"
echo ""
echo "[*] Backend API:  http://localhost:5001"
echo "[*] Frontend UI:  http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
