#!/usr/bin/env python
"""
Start LiveLink WebSocket Server

Usage:
    python scripts/start-livelink-ws.py [--port PORT] [--mode MODE]

Options:
    --port PORT   Port to run on (default: 5001, auto-finds available if busy)
    --mode MODE   LiveLink mode: auto, wcf, simulation (default: simulation)

The server provides:
    - WebSocket endpoint at ws://localhost:PORT/livelink
    - REST status endpoint at http://localhost:PORT/status
    - Test page at http://localhost:PORT/
"""

import argparse
import socket
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts}"
    )


def main():
    parser = argparse.ArgumentParser(description="Start LiveLink WebSocket Server")
    parser.add_argument("--port", type=int, default=5001, help="Port to run on")
    parser.add_argument(
        "--mode",
        choices=["auto", "wcf", "simulation"],
        default="simulation",
        help="LiveLink mode",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    args = parser.parse_args()

    # Find available port
    try:
        port = find_available_port(args.port)
        if port != args.port:
            print(f"Port {args.port} busy, using port {port}")
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("=" * 50)
    print("DynoAI LiveLink WebSocket Server")
    print("=" * 50)
    print(f"Mode: {args.mode}")
    print(f"Host: {args.host}")
    print(f"Port: {port}")
    print()
    print(f"REST API:   http://{args.host}:{port}/status")
    print(f"Test Page:  http://{args.host}:{port}/")
    print(f"WebSocket:  ws://{args.host}:{port}/livelink")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 50)

    from api.services.livelink_websocket import run_standalone

    try:
        run_standalone(host=args.host, port=port, mode=args.mode)
    except KeyboardInterrupt:
        print("\nServer stopped")


if __name__ == "__main__":
    main()
