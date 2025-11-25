"""Jetstream API routes blueprint."""

from flask import Blueprint

from .config import config_bp
from .progress import progress_bp
from .runs import runs_bp
from .status import status_bp
from .sync import sync_bp

# Create main jetstream blueprint
jetstream_bp = Blueprint("jetstream", __name__)

# Register sub-blueprints
jetstream_bp.register_blueprint(config_bp)
jetstream_bp.register_blueprint(status_bp)
jetstream_bp.register_blueprint(runs_bp)
jetstream_bp.register_blueprint(sync_bp)
jetstream_bp.register_blueprint(progress_bp)

__all__ = ["jetstream_bp"]
