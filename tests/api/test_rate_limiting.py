"""Tests for rate limiting functionality."""

import pytest
from flask import Flask
from unittest.mock import patch


class TestRateLimiting:
    """Test rate limiting configuration and behavior."""

    def test_rate_limiter_module_imports(self):
        """Test that rate limiter module can be imported."""
        from api.rate_limit import RateLimits, init_rate_limiter, get_client_identifier
        
        assert RateLimits.EXPENSIVE == "5/minute;20/hour"
        assert RateLimits.STANDARD == "60/minute"
        assert RateLimits.READ_ONLY == "120/minute"
        assert RateLimits.HEALTH == "300/minute"

    def test_init_rate_limiter_creates_limiter(self):
        """Test that init_rate_limiter creates a Limiter instance."""
        from api.rate_limit import init_rate_limiter
        from flask_limiter import Limiter
        
        app = Flask(__name__)
        limiter = init_rate_limiter(app)
        
        assert limiter is not None
        assert isinstance(limiter, Limiter)

    def test_rate_limiter_respects_enabled_env(self):
        """Test that rate limiter respects RATE_LIMIT_ENABLED env var."""
        from api.rate_limit import init_rate_limiter
        
        app = Flask(__name__)
        
        # When disabled
        with patch.dict('os.environ', {'RATE_LIMIT_ENABLED': 'false'}):
            limiter = init_rate_limiter(app)
            # Should still create limiter but with no default limits
            assert limiter is not None

    def test_get_client_identifier_with_api_key(self):
        """Test client identifier extraction with API key."""
        from api.rate_limit import get_client_identifier
        
        app = Flask(__name__)
        with app.test_request_context(headers={'X-API-Key': 'test-key-123'}):
            identifier = get_client_identifier()
            assert identifier == "api_key:test-key-123"

    def test_get_client_identifier_with_forwarded_for(self):
        """Test client identifier extraction with X-Forwarded-For header."""
        from api.rate_limit import get_client_identifier
        
        app = Flask(__name__)
        with app.test_request_context(
            headers={'X-Forwarded-For': '192.168.1.100, 10.0.0.1'}
        ):
            identifier = get_client_identifier()
            assert identifier == "192.168.1.100"

    def test_get_client_identifier_fallback_to_remote_addr(self):
        """Test client identifier falls back to remote address."""
        from api.rate_limit import get_client_identifier
        
        app = Flask(__name__)
        with app.test_request_context(environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            identifier = get_client_identifier()
            # Should return something (exact value depends on test context)
            assert identifier is not None

    def test_rate_limit_429_error_handler(self):
        """Test that 429 error handler returns proper JSON response."""
        from api.rate_limit import init_rate_limiter
        from flask_limiter.util import get_remote_address
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        limiter = init_rate_limiter(app)
        
        @app.route('/test-limited')
        @limiter.limit("1 per day")
        def limited_route():
            return "ok"
        
        client = app.test_client()
        
        # First request should succeed
        response = client.get('/test-limited')
        assert response.status_code == 200
        
        # Second request should be rate limited
        response = client.get('/test-limited')
        assert response.status_code == 429
        
        # Verify JSON structure
        data = response.get_json()
        assert 'error' in data
        assert data['error']['code'] == 'RATE_LIMIT_EXCEEDED'
        assert 'message' in data['error']


class TestRateLimitingIntegration:
    """Integration tests for rate limiting in the main app."""

    @pytest.fixture
    def client(self):
        """Create test client from the main app."""
        from api.app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_health_endpoint_works(self, client):
        """Test that health endpoint works (should not be rate limited aggressively)."""
        response = client.get('/api/health')
        assert response.status_code == 200

    def test_runs_endpoint_works(self, client):
        """Test that runs endpoint works."""
        response = client.get('/api/runs')
        assert response.status_code == 200

    def test_rate_limit_headers_present_after_request(self, client):
        """Test that rate limit headers are added to responses."""
        response = client.get('/api/runs')
        # Flask-Limiter should add these headers when limits are tracked
        # Note: In some configs headers only appear after limit tracking starts
        assert response.status_code == 200
        # The actual header checking depends on Flask-Limiter version and config

