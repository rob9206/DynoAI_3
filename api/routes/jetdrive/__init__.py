"""JetDrive Auto-Tune API Routes (sub-blueprint package)."""

from flask import Blueprint

jetdrive_bp = Blueprint("jetdrive", __name__, url_prefix="/api/jetdrive")

from .analysis import analysis_bp  # noqa: E402
from .hardware import hardware_bp  # noqa: E402
from .innovate import innovate_bp  # noqa: E402
from .mapping import mapping_bp  # noqa: E402
from .simulator import simulator_bp  # noqa: E402

jetdrive_bp.register_blueprint(analysis_bp)
jetdrive_bp.register_blueprint(hardware_bp)
jetdrive_bp.register_blueprint(mapping_bp)
jetdrive_bp.register_blueprint(innovate_bp)
jetdrive_bp.register_blueprint(simulator_bp)

__all__ = ["jetdrive_bp"]
