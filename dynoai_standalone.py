#!/usr/bin/env python3
"""
DynoAI Standalone Executable Entry Point
Bundles Flask API + React frontend into a single application
"""

import os
import sys
import threading
import webbrowser
import time
from pathlib import Path


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return base_path / relative_path


def setup_environment():
    """Configure environment for standalone operation"""
    # Set working directory
    if hasattr(sys, '_MEIPASS'):
        os.chdir(sys._MEIPASS)
    else:
        os.chdir(Path(__file__).parent)
    
    # Add current directory to path for imports
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    
    # Ensure required directories exist in user's home folder (persistent storage)
    app_data = Path.home() / "DynoAI"
    (app_data / "uploads").mkdir(parents=True, exist_ok=True)
    (app_data / "outputs").mkdir(parents=True, exist_ok=True)
    (app_data / "runs").mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for data storage
    os.environ["DYNOAI_UPLOAD_DIR"] = str(app_data / "uploads")
    os.environ["DYNOAI_OUTPUT_DIR"] = str(app_data / "outputs")
    os.environ["DYNOAI_RUNS_DIR"] = str(app_data / "runs")
    os.environ["DYNOAI_DEBUG"] = "false"
    os.environ["DYNOAI_STANDALONE"] = "true"  # Flag for standalone mode
    
    return app_data


def open_browser(port):
    """Open browser after a short delay"""
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{port}")


def print_banner(port, data_dir):
    """Print startup banner"""
    print()
    print("=" * 60)
    print("  DynoAI - Standalone Desktop Application v1.2.1")
    print("=" * 60)
    print()
    print(f"  [*] Application: http://127.0.0.1:{port}")
    print(f"  [*] Data folder: {data_dir}")
    print()
    print("  Press Ctrl+C to quit")
    print()
    print("=" * 60)
    print()


def main():
    """Main entry point for standalone application"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DynoAI Standalone Application")
    parser.add_argument("--port", type=int, default=5001, help="Port to run on (default: 5001)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Setup environment BEFORE importing Flask app
    data_dir = setup_environment()
    
    if args.debug:
        os.environ["DYNOAI_DEBUG"] = "true"
    
    # Import the Flask app from api.app (this already has all routes registered)
    # The DYNOAI_STANDALONE env var tells api.app to skip the root route
    from api.app import app
    from flask import send_from_directory
    
    # Get path to frontend dist folder
    frontend_dist = get_resource_path("frontend/dist")
    
    # Register frontend serving routes
    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        """Serve static assets from React build"""
        return send_from_directory(frontend_dist / 'assets', filename)
    
    @app.route('/', defaults={'path': ''}, methods=['GET'])
    @app.route('/<path:path>', methods=['GET'])
    def serve_frontend(path):
        """Serve the React frontend for non-API routes"""
        # Don't intercept API routes, admin, or metrics
        if path.startswith('api/') or path.startswith('admin') or path == 'metrics':
            from flask import abort
            abort(404)
        
        # Serve static files if they exist
        static_file = frontend_dist / path
        if path and static_file.exists() and static_file.is_file():
            return send_from_directory(frontend_dist, path)
        
        # Otherwise serve index.html for client-side routing
        return send_from_directory(frontend_dist, 'index.html')
    
    # Print banner
    print_banner(args.port, data_dir)
    
    # Open browser in background thread
    if not args.no_browser:
        browser_thread = threading.Thread(target=open_browser, args=(args.port,), daemon=True)
        browser_thread.start()
    
    # Run the server
    try:
        # Use waitress for production if available
        try:
            from waitress import serve
            print("[*] Starting production server (Waitress)...")
            serve(app, host="127.0.0.1", port=args.port, threads=4)
        except ImportError:
            print("[*] Starting Flask development server...")
            app.run(host="127.0.0.1", port=args.port, debug=args.debug, threaded=True)
    except KeyboardInterrupt:
        print("\n[*] Shutting down DynoAI...")
        sys.exit(0)


if __name__ == "__main__":
    main()
