"""YourDyno integration routes."""

from flask import Blueprint

yourdyno_bp = Blueprint("yourdyno", __name__, url_prefix="/api/yourdyno")

from .live import live_bp  # noqa: E402

yourdyno_bp.register_blueprint(live_bp)

__all__ = ["yourdyno_bp"]
