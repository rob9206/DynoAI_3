"""
Reliability Agent Flask Integration

Helper to integrate reliability agent with Flask application.
"""

import logging
from flask import Flask

from api.reliability_agent import get_reliability_agent
from api.routes.reliability import reliability_bp

logger = logging.getLogger(__name__)


def init_reliability(app: Flask):
    """
    Initialize reliability agent with Flask application.
    
    Args:
        app: Flask application instance
        
    Usage:
        from api.reliability_integration import init_reliability
        
        app = Flask(__name__)
        init_reliability(app)
    """
    # Register blueprint
    app.register_blueprint(reliability_bp, url_prefix="/api")
    
    # Get agent instance (creates if needed)
    agent = get_reliability_agent()
    
    logger.info("[Reliability] Reliability agent initialized")
    logger.info("[Reliability] Available at /api/reliability/*")
    
    return agent

