"""
Run history endpoints for DynoAI.

Endpoints:
  GET /api/runs          — list runs (role-filtered, paginated)
  GET /api/runs/<run_id> — get single run details
"""

import json
import logging

from flask import Blueprint, g, jsonify, request

from api.middleware.auth_middleware import require_jwt
from api.services.database import SessionLocal

logger = logging.getLogger(__name__)

runs_bp = Blueprint("runs", __name__, url_prefix="/api")


def _build_run_dict(run, user):
    """Serialise a Run ORM object to the frontend response shape."""
    return {
        "runId": run.run_id,
        "userId": str(run.user_id) if run.user_id else None,
        "userEmail": user.email if user else None,
        "userName": user.name if user else None,
        "status": run.status,
        "inputFile": run.input_file,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
        "completedAt": run.completed_at.isoformat() if run.completed_at else None,
        "rowsProcessed": run.rows_processed,
        "correctionsApplied": run.corrections_applied,
        "analysisMetrics": {
            "avgCorrection": run.avg_correction,
            "maxCorrection": run.max_correction,
        },
        "outputFiles": json.loads(run.output_files) if run.output_files else [],
    }


@runs_bp.route("/runs", methods=["GET"])
@require_jwt
def list_runs():
    """
    GET /api/runs — list analysis runs.

    Role behaviour:
      customer → own runs only
      tech / owner → all runs

    Query params (all optional):
      limit:  int  default 50, max 200
      offset: int  default 0
      status: str  filter by status string
    """
    from api.models.run import Run
    from api.models.user import User

    current_user = g.current_user
    role = current_user.get("role", "customer")

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        offset = 0

    status_filter = request.args.get("status")

    with SessionLocal() as session:
        query = session.query(Run)

        if role == "customer":
            query = query.filter(Run.user_id == current_user["id"])

        if status_filter:
            query = query.filter(Run.status == status_filter)

        total = query.count()

        runs = (
            query.order_by(Run.created_at.desc()).offset(offset).limit(limit).all()
        )

        # Collect user IDs and fetch in one query
        user_ids = {r.user_id for r in runs if r.user_id}
        users_by_id = {}
        if user_ids:
            users = session.query(User).filter(User.id.in_(user_ids)).all()
            users_by_id = {u.id: u for u in users}

        runs_list = [
            _build_run_dict(run, users_by_id.get(run.user_id)) for run in runs
        ]

    return (
        jsonify(
            {
                "runs": runs_list,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        ),
        200,
    )


@runs_bp.route("/runs/<run_id>", methods=["GET"])
@require_jwt
def get_run(run_id):
    """
    GET /api/runs/<run_id> — get a single run by its run_id.

    Customers may only retrieve their own runs (403 if not the owner).
    Tech / owner may retrieve any run.
    """
    from api.models.run import Run
    from api.models.user import User

    current_user = g.current_user
    role = current_user.get("role", "customer")

    with SessionLocal() as session:
        run = session.query(Run).filter(Run.run_id == run_id).first()

        if run is None:
            return jsonify({"error": "Run not found"}), 404

        if role == "customer" and run.user_id != current_user["id"]:
            return jsonify({"error": "Access denied"}), 403

        user = session.get(User, run.user_id) if run.user_id else None
        result = _build_run_dict(run, user)

    return jsonify(result), 200
