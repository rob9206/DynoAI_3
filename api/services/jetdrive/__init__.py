"""
JetDrive Hardware Integration Services.

Provides UDP multicast discovery, real-time data acquisition,
channel mapping, data validation, preflight checks, and live
analysis for Dynojet dynos.

Modules:
    jetdrive_client        - UDP multicast protocol (224.0.2.10:22344)
    jetdrive_validation    - Channel health monitoring
    jetdrive_mapping       - Channel name mapping & transforms
    jetdrive_live_queue    - 50ms sample aggregation (20Hz UI)
    jetdrive_preflight     - Pre-session validation
    jetdrive_realtime_analysis - Live coverage & VE delta tracking

Live Data Transport:
    The backend exposes both HTTP polling (GET /hardware/live/data)
    and Server-Sent Events (GET /hardware/live/stream) for real-time
    channel data.  SSE is preferred (lower latency, reduced server
    load) and is enabled by default in the frontend useJetDriveLive
    hook.  Full WebSocket was evaluated and deemed unnecessary since
    the data flow is unidirectional (server -> client); SSE provides
    equivalent push semantics with simpler infrastructure.
"""
