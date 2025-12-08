"""
LiveLink WebSocket Server

Provides real-time WebSocket streaming of dyno data to web clients.
Uses Flask-SocketIO for WebSocket support.

Events:
    Client -> Server:
        'connect'     - Client connects
        'disconnect'  - Client disconnects
        'subscribe'   - Subscribe to specific channels
        'unsubscribe' - Unsubscribe from channels

    Server -> Client:
        'data'        - Real-time data sample
        'snapshot'    - Full data snapshot
        'status'      - Connection status update
        'error'       - Error message

Usage:
    from flask import Flask
    from flask_socketio import SocketIO
    from api.services.livelink_websocket import init_livelink_socketio

    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    # Initialize LiveLink WebSocket events
    init_livelink_socketio(socketio)

    # Run with WebSocket support
    socketio.run(app, host="0.0.0.0", port=5000)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from api.services.livelink_client import LiveDataSample, LiveLinkClient

if TYPE_CHECKING:
    from flask_socketio import SocketIO


@dataclass
class ClientSubscription:
    """Tracks a client's channel subscriptions."""

    sid: str
    channels: set[str] = field(default_factory=set)
    all_channels: bool = True


class LiveLinkSocketIOManager:
    """
    Manages WebSocket connections for LiveLink data streaming.

    Handles:
    - Client connections/disconnections
    - Channel subscriptions
    - Data broadcasting
    - Snapshot requests
    """

    def __init__(self, socketio: "SocketIO", namespace: str = "/livelink") -> None:
        self.socketio = socketio
        self.namespace = namespace
        self.client: Optional[LiveLinkClient] = None
        self.subscriptions: dict[str, ClientSubscription] = {}
        self._lock = threading.Lock()
        self._snapshot_interval = 1.0  # Seconds between snapshot broadcasts
        self._snapshot_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self, mode: str = "auto") -> bool:
        """Start the LiveLink client and begin streaming."""
        if self.client and self.client.connected:
            return True

        self.client = LiveLinkClient(mode=mode)
        self.client.on_data(self._on_data)

        if self.client.connect():
            self._running = True
            self._snapshot_thread = threading.Thread(
                target=self._snapshot_loop, daemon=True
            )
            self._snapshot_thread.start()

            self.socketio.emit(
                "status",
                {
                    "connected": True,
                    "mode": self.client.mode,
                    "message": "LiveLink connected",
                },
                namespace=self.namespace,
            )
            return True

        return False

    def stop(self) -> None:
        """Stop the LiveLink client and streaming."""
        self._running = False

        if self._snapshot_thread and self._snapshot_thread.is_alive():
            self._snapshot_thread.join(timeout=2.0)

        if self.client:
            self.client.disconnect()

        self.socketio.emit(
            "status",
            {
                "connected": False,
                "mode": None,
                "message": "LiveLink disconnected",
            },
            namespace=self.namespace,
        )

    def add_client(self, sid: str) -> None:
        """Add a new client connection."""
        with self._lock:
            self.subscriptions[sid] = ClientSubscription(sid=sid)

        # Send current snapshot to new client
        if self.client and self.client.connected:
            snapshot = self.client.get_snapshot()
            self.socketio.emit(
                "snapshot",
                {
                    "timestamp": snapshot.timestamp,
                    "channels": snapshot.channels,
                    "units": snapshot.units,
                },
                room=sid,
                namespace=self.namespace,
            )

    def remove_client(self, sid: str) -> None:
        """Remove a client connection."""
        with self._lock:
            if sid in self.subscriptions:
                del self.subscriptions[sid]

    def subscribe(self, sid: str, channels: list[str]) -> None:
        """Subscribe a client to specific channels."""
        with self._lock:
            if sid in self.subscriptions:
                sub = self.subscriptions[sid]
                sub.all_channels = False
                sub.channels.update(channels)

    def unsubscribe(self, sid: str, channels: list[str]) -> None:
        """Unsubscribe a client from specific channels."""
        with self._lock:
            if sid in self.subscriptions:
                sub = self.subscriptions[sid]
                sub.channels.difference_update(channels)

    def subscribe_all(self, sid: str) -> None:
        """Subscribe a client to all channels."""
        with self._lock:
            if sid in self.subscriptions:
                sub = self.subscriptions[sid]
                sub.all_channels = True
                sub.channels.clear()

    def _on_data(self, sample: LiveDataSample) -> None:
        """Handle incoming data from LiveLink client."""
        data = {
            "timestamp": sample.timestamp,
            "channel_id": sample.channel_id,
            "channel": sample.channel_name,
            "value": sample.value,
            "units": sample.units,
        }

        # Broadcast to subscribed clients
        with self._lock:
            for sid, sub in self.subscriptions.items():
                if sub.all_channels or sample.channel_name in sub.channels:
                    self.socketio.emit("data", data, room=sid, namespace=self.namespace)

    def _snapshot_loop(self) -> None:
        """Periodically broadcast full snapshots."""
        while self._running:
            if self.client and self.client.connected:
                snapshot = self.client.get_snapshot()
                self.socketio.emit(
                    "snapshot",
                    {
                        "timestamp": snapshot.timestamp,
                        "channels": snapshot.channels,
                        "units": snapshot.units,
                    },
                    namespace=self.namespace,
                )

            time.sleep(self._snapshot_interval)


# Global manager instance
_manager: Optional[LiveLinkSocketIOManager] = None


def get_manager() -> Optional[LiveLinkSocketIOManager]:
    """Get the global LiveLink SocketIO manager."""
    return _manager


def init_livelink_socketio(
    socketio: "SocketIO",
    namespace: str = "/livelink",
    auto_start: bool = False,
    mode: str = "auto",
) -> LiveLinkSocketIOManager:
    """
    Initialize LiveLink WebSocket events on a Flask-SocketIO instance.

    Args:
        socketio: Flask-SocketIO instance
        namespace: WebSocket namespace (default: /livelink)
        auto_start: Automatically start LiveLink connection
        mode: LiveLink mode ("auto", "wcf", "simulation")

    Returns:
        LiveLinkSocketIOManager instance
    """
    global _manager
    _manager = LiveLinkSocketIOManager(socketio)

    # Register event handlers
    @socketio.on("connect", namespace=namespace)
    def handle_connect():
        from flask import request

        sid = request.sid
        _manager.add_client(sid)

        socketio.emit(
            "status",
            {
                "connected": _manager.client.connected if _manager.client else False,
                "mode": _manager.client.mode if _manager.client else None,
                "message": "Connected to LiveLink WebSocket",
            },
            room=sid,
        )

    @socketio.on("disconnect", namespace=namespace)
    def handle_disconnect():
        from flask import request

        sid = request.sid
        _manager.remove_client(sid)

    @socketio.on("start", namespace=namespace)
    def handle_start(data=None):
        """Start LiveLink streaming."""
        mode = data.get("mode", "auto") if data else "auto"
        success = _manager.start(mode=mode)
        return {"success": success}

    @socketio.on("stop", namespace=namespace)
    def handle_stop():
        """Stop LiveLink streaming."""
        _manager.stop()
        return {"success": True}

    @socketio.on("subscribe", namespace=namespace)
    def handle_subscribe(data):
        """Subscribe to specific channels."""
        from flask import request

        sid = request.sid
        channels = data.get("channels", [])
        if channels:
            _manager.subscribe(sid, channels)
        else:
            _manager.subscribe_all(sid)
        return {"success": True, "channels": channels}

    @socketio.on("unsubscribe", namespace=namespace)
    def handle_unsubscribe(data):
        """Unsubscribe from specific channels."""
        from flask import request

        sid = request.sid
        channels = data.get("channels", [])
        _manager.unsubscribe(sid, channels)
        return {"success": True}

    @socketio.on("get_snapshot", namespace=namespace)
    def handle_get_snapshot(data=None):
        """Request current data snapshot."""
        if _manager.client and _manager.client.connected:
            snapshot = _manager.client.get_snapshot()
            return {
                "success": True,
                "timestamp": snapshot.timestamp,
                "channels": snapshot.channels,
                "units": snapshot.units,
            }
        return {"success": False, "error": "Not connected"}

    @socketio.on("get_channel", namespace=namespace)
    def handle_get_channel(data=None):
        """Request specific channel value."""
        data = data or {}
        channel = data.get("channel")
        if not channel:
            return {"success": False, "error": "No channel specified"}

        if _manager.client and _manager.client.connected:
            value = _manager.client.get_channel_value(channel)
            snapshot = _manager.client.get_snapshot()
            if value is not None:
                return {
                    "success": True,
                    "channel": channel,
                    "value": value,
                    "units": snapshot.units.get(channel, ""),
                }
            return {"success": False, "error": f"Channel not found: {channel}"}
        return {"success": False, "error": "Not connected"}

    # Auto-start if requested
    if auto_start:
        _manager.start(mode=mode)

    return _manager


# =============================================================================
# Standalone WebSocket Server
# =============================================================================


def create_livelink_app(
    host: str = "0.0.0.0",
    port: int = 5001,
    mode: str = "auto",
    cors_origins: str = "*",
) -> tuple:
    """
    Create a standalone Flask app with LiveLink WebSocket support.

    Returns:
        Tuple of (Flask app, SocketIO instance, LiveLinkSocketIOManager)

    Usage:
        app, socketio, manager = create_livelink_app()
        socketio.run(app, host="0.0.0.0", port=5001)
    """
    from flask import Flask
    from flask_cors import CORS
    from flask_socketio import SocketIO

    app = Flask(__name__)
    CORS(app, origins=cors_origins)
    socketio = SocketIO(app, cors_allowed_origins=cors_origins, async_mode="eventlet")

    manager = init_livelink_socketio(socketio, auto_start=True, mode=mode)

    # Add REST endpoints for status
    @app.route("/status")
    def status():
        if manager.client:
            return {
                "connected": manager.client.connected,
                "mode": manager.client.mode,
                "clients": len(manager.subscriptions),
            }
        return {"connected": False, "mode": None, "clients": 0}

    @app.route("/")
    def index():
        return """
<!DOCTYPE html>
<html>
<head>
    <title>LiveLink WebSocket Test</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }
        .channel { display: inline-block; width: 200px; margin: 5px; padding: 10px;
                   background: #16213e; border-radius: 5px; }
        .value { font-size: 24px; color: #0f0; }
        .units { color: #888; font-size: 12px; }
        h1 { color: #e94560; }
        #status { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .connected { background: #1b4332; }
        .disconnected { background: #7f1d1d; }
    </style>
</head>
<body>
    <h1>🏍️ DynoAI LiveLink</h1>
    <div id="status" class="disconnected">Disconnected</div>
    <div id="channels"></div>

    <script>
        const socket = io('/livelink');
        const channels = {};

        socket.on('connect', () => {
            document.getElementById('status').textContent = 'Connected to WebSocket';
            document.getElementById('status').className = 'connected';
            socket.emit('start', {mode: 'simulation'});
        });

        socket.on('disconnect', () => {
            document.getElementById('status').textContent = 'Disconnected';
            document.getElementById('status').className = 'disconnected';
        });

        socket.on('status', (data) => {
            document.getElementById('status').textContent =
                `LiveLink: ${data.connected ? 'Connected' : 'Disconnected'} (${data.mode || 'none'})`;
        });

        socket.on('data', (data) => {
            updateChannel(data.channel, data.value, data.units);
        });

        socket.on('snapshot', (data) => {
            for (const [channel, value] of Object.entries(data.channels)) {
                updateChannel(channel, value, data.units[channel] || '');
            }
        });

        function updateChannel(name, value, units) {
            let el = channels[name];
            if (!el) {
                el = document.createElement('div');
                el.className = 'channel';
                el.innerHTML = `<div class="name">${name}</div>
                               <div class="value">--</div>
                               <div class="units">${units}</div>`;
                document.getElementById('channels').appendChild(el);
                channels[name] = el;
            }
            el.querySelector('.value').textContent = value.toFixed(2);
        }
    </script>
</body>
</html>
"""

    return app, socketio, manager


def run_standalone(host: str = "0.0.0.0", port: int = 5001, mode: str = "simulation"):
    """Run standalone LiveLink WebSocket server."""
    app, socketio, _ = create_livelink_app(host=host, port=port, mode=mode)
    print(f"Starting LiveLink WebSocket server on http://{host}:{port}")
    print(f"WebSocket endpoint: ws://{host}:{port}/livelink")
    socketio.run(app, host=host, port=port)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ClientSubscription",
    "LiveLinkSocketIOManager",
    "create_livelink_app",
    "get_manager",
    "init_livelink_socketio",
    "run_standalone",
]


if __name__ == "__main__":
    run_standalone()
