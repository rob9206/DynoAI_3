"""Test the LiveLink WebSocket module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_module_imports():
    """Test that all WebSocket components can be imported."""
    from api.services.livelink_websocket import (
        ClientSubscription,
        LiveLinkSocketIOManager,
        create_livelink_app,
        get_manager,
        init_livelink_socketio,
    )

    print("✓ All imports successful")

    # Test ClientSubscription
    sub = ClientSubscription(sid="test_client")
    assert sub.sid == "test_client"
    assert sub.all_channels is True
    assert len(sub.channels) == 0
    print("✓ ClientSubscription works")


def test_create_app():
    """Test that the Flask app can be created."""
    from api.services.livelink_websocket import create_livelink_app

    app, socketio, manager = create_livelink_app(mode="simulation")

    assert app is not None
    assert socketio is not None
    assert manager is not None
    print("✓ Flask app created successfully")

    # Test the status endpoint
    with app.test_client() as client:
        response = client.get("/status")
        assert response.status_code == 200
        data = response.get_json()
        print(f"  Status: {data}")


def test_websocket_manager():
    """Test the WebSocket manager."""
    from unittest.mock import MagicMock

    from api.services.livelink_websocket import LiveLinkSocketIOManager

    # Create mock SocketIO
    mock_socketio = MagicMock()
    manager = LiveLinkSocketIOManager(mock_socketio)

    # Test client management
    manager.add_client("client1")
    assert "client1" in manager.subscriptions
    print("✓ Client added")

    # Test subscription
    manager.subscribe("client1", ["Engine RPM", "MAP kPa"])
    sub = manager.subscriptions["client1"]
    assert "Engine RPM" in sub.channels
    assert sub.all_channels is False
    print("✓ Subscription works")

    # Test unsubscription
    manager.unsubscribe("client1", ["MAP kPa"])
    assert "MAP kPa" not in sub.channels
    print("✓ Unsubscription works")

    # Test remove client
    manager.remove_client("client1")
    assert "client1" not in manager.subscriptions
    print("✓ Client removed")


if __name__ == "__main__":
    print("=== LiveLink WebSocket Tests ===\n")
    test_module_imports()
    print()
    test_create_app()
    print()
    test_websocket_manager()
    print("\n=== All Tests Passed ===")

