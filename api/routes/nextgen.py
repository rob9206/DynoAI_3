"""
DynoAI NextGen API Routes

Provides REST endpoints for NextGen physics-informed analysis:
- POST /api/nextgen/<run_id>/generate  - Generate NextGen analysis
- GET  /api/nextgen/<run_id>           - Get cached analysis payload
- GET  /api/nextgen/<run_id>/download  - Download analysis JSON

The NextGen workflow produces:
- Mode-labeled operating regions
- 2D surfaces (spark, AFR error, knock)
- Spark valley detection
- Causal hypothesis ranking
- Next-test recommendations
"""

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from api.services.nextgen_workflow import (
    get_nextgen_workflow,
    TestPlannerConstraints,
    get_planner_constraints,
    save_planner_constraints,
)
from api.services.coverage_tracker import (
    aggregate_run_coverage,
    get_cumulative_gaps,
    get_coverage_summary,
    load_cumulative_coverage,
    reset_cumulative_coverage,
)

__all__ = ["nextgen_bp"]

nextgen_bp = Blueprint("nextgen", __name__, url_prefix="/api/nextgen")


@nextgen_bp.route("/<run_id>/generate", methods=["POST"])
def generate_analysis(run_id: str):
    """
    Generate NextGen analysis for a run.
    
    URL Parameters:
        run_id: The run ID to analyze
        
    Query Parameters:
        force: If "true", regenerate even if cached (default: false)
        include: If "full", include payload in response (default: summary only)
        
    Returns:
        {
            "success": true,
            "run_id": "...",
            "generated_at": "2024-01-15T10:30:00Z",
            "from_cache": false,
            "summary": {
                "total_samples": 1500,
                "surface_count": 4,
                "hypothesis_count": 3,
                ...
            },
            "download_url": "/api/nextgen/.../download",
            "payload": {...}  // Only if include=full
        }
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    # Parse query parameters
    force = request.args.get("force", "false").lower() == "true"
    include_full = request.args.get("include", "summary").lower() == "full"
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Generate analysis
    result = workflow.generate_for_run(run_id, force=force)
    
    if not result["success"]:
        error_msg = result.get("error", "Unknown error")
        return jsonify({
            "success": False,
            "run_id": run_id,
            "error": error_msg,
        }), 400
    
    # Build response
    response = {
        "success": True,
        "run_id": run_id,
        "generated_at": result["generated_at"],
        "from_cache": result["from_cache"],
        "summary": result["summary"],
        "download_url": result["download_url"],
    }
    
    # Include full payload if requested
    if include_full:
        response["payload"] = result["payload"]
    
    return jsonify(response), 200


@nextgen_bp.route("/<run_id>", methods=["GET"])
def get_analysis(run_id: str):
    """
    Get cached NextGen analysis payload.
    
    URL Parameters:
        run_id: The run ID
        
    Returns:
        Full NextGenAnalysisPayload JSON or 404 if not found
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Load cached payload
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"NextGen analysis not found for run {run_id}",
            "hint": f"Generate analysis first: POST /api/nextgen/{run_id}/generate",
        }), 404
    
    return jsonify(cached), 200


@nextgen_bp.route("/<run_id>/download", methods=["GET"])
def download_analysis(run_id: str):
    """
    Download NextGen analysis as JSON file attachment.
    
    URL Parameters:
        run_id: The run ID
        
    Returns:
        NextGenAnalysis.json as file download
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Get payload path
    payload_path = workflow.get_payload_path(run_id)
    
    if payload_path is None or not payload_path.exists():
        return jsonify({
            "error": f"NextGen analysis file not found for run {run_id}",
            "hint": f"Generate analysis first: POST /api/nextgen/{run_id}/generate",
        }), 404
    
    return send_file(
        payload_path,
        as_attachment=True,
        download_name=f"NextGenAnalysis_{run_id}.json",
        mimetype="application/json",
    )


@nextgen_bp.route("/<run_id>/summary", methods=["GET"])
def get_summary(run_id: str):
    """
    Get analysis summary without full payload.
    
    URL Parameters:
        run_id: The run ID
        
    Returns:
        Summary statistics and top findings
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Load cached payload
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"NextGen analysis not found for run {run_id}",
        }), 404
    
    # Extract summary
    summary = workflow._build_summary(cached)
    summary["run_id"] = run_id
    summary["generated_at"] = cached.get("generated_at")
    summary["schema_version"] = cached.get("schema_version")
    
    return jsonify(summary), 200


@nextgen_bp.route("/<run_id>/surfaces", methods=["GET"])
def get_surfaces(run_id: str):
    """
    Get surface data from analysis.
    
    URL Parameters:
        run_id: The run ID
        
    Query Parameters:
        surface_id: Optional specific surface to retrieve
        
    Returns:
        Surface data formatted for visualization
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    surface_id = request.args.get("surface_id")
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Load cached payload
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"NextGen analysis not found for run {run_id}",
        }), 404
    
    surfaces = cached.get("surfaces", {})
    
    if surface_id:
        if surface_id not in surfaces:
            return jsonify({
                "error": f"Surface '{surface_id}' not found",
                "available_surfaces": list(surfaces.keys()),
            }), 404
        return jsonify(surfaces[surface_id]), 200
    
    return jsonify({
        "surfaces": surfaces,
        "surface_ids": list(surfaces.keys()),
    }), 200


@nextgen_bp.route("/<run_id>/hypotheses", methods=["GET"])
def get_hypotheses(run_id: str):
    """
    Get cause tree hypotheses from analysis.
    
    URL Parameters:
        run_id: The run ID
        
    Query Parameters:
        min_confidence: Minimum confidence threshold (0.0-1.0)
        category: Filter by category
        
    Returns:
        Ranked list of hypotheses with evidence
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    min_confidence = float(request.args.get("min_confidence", 0.0))
    category_filter = request.args.get("category")
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Load cached payload
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"NextGen analysis not found for run {run_id}",
        }), 404
    
    cause_tree = cached.get("cause_tree", {})
    hypotheses = cause_tree.get("hypotheses", [])
    
    # Apply filters
    filtered = [
        h for h in hypotheses
        if h.get("confidence", 0) >= min_confidence
    ]
    
    if category_filter:
        filtered = [
            h for h in filtered
            if h.get("category") == category_filter
        ]
    
    return jsonify({
        "hypotheses": filtered,
        "total_count": len(hypotheses),
        "filtered_count": len(filtered),
        "summary": cause_tree.get("summary"),
    }), 200


@nextgen_bp.route("/<run_id>/test-plan", methods=["GET"])
def get_test_plan(run_id: str):
    """
    Get next-test recommendations from analysis.
    
    URL Parameters:
        run_id: The run ID
        
    Query Parameters:
        max_priority: Maximum priority level to include (1=highest)
        
    Returns:
        Prioritized list of test steps
    """
    # Sanitize run_id
    run_id = secure_filename(run_id)
    if not run_id:
        return jsonify({"error": "Invalid run_id"}), 400
    
    max_priority = int(request.args.get("max_priority", 99))
    
    # Get workflow service
    workflow = get_nextgen_workflow()
    
    # Load cached payload
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"NextGen analysis not found for run {run_id}",
        }), 404
    
    next_tests = cached.get("next_tests", {})
    steps = next_tests.get("steps", [])
    
    # Filter by priority
    filtered = [s for s in steps if s.get("priority", 99) <= max_priority]
    
    return jsonify({
        "steps": filtered,
        "total_count": len(steps),
        "filtered_count": len(filtered),
        "priority_rationale": next_tests.get("priority_rationale"),
        "coverage_gaps": next_tests.get("coverage_gaps", []),
    }), 200


# =============================================================================
# Phase 7: Predictive Test Planning Endpoints
# =============================================================================

@nextgen_bp.route("/planner/cumulative-coverage", methods=["GET"])
def get_cumulative_coverage_endpoint():
    """
    Get aggregated coverage for a vehicle across all runs.
    
    Query Parameters:
        vehicle_id: Vehicle identifier (default: "default")
        
    Returns:
        {
            "vehicle_id": "...",
            "dyno_signature": "...",
            "total_runs": 5,
            "run_ids": [...],
            "surfaces": ["spark_f", "afr_error_f", ...],
            "total_cells": 200,
            "covered_cells": 145,
            "coverage_pct": 72.5,
            "last_updated": "...",
            "created_at": "..."
        }
    """
    vehicle_id = request.args.get("vehicle_id", "default")
    
    summary = get_coverage_summary(vehicle_id)
    
    if summary is None:
        return jsonify({
            "error": f"No coverage data found for vehicle {vehicle_id}",
            "vehicle_id": vehicle_id,
        }), 404
    
    return jsonify(summary), 200


@nextgen_bp.route("/planner/cumulative-gaps", methods=["GET"])
def get_cumulative_gaps_endpoint():
    """
    Get coverage gaps based on cumulative coverage.
    
    Query Parameters:
        vehicle_id: Vehicle identifier (default: "default")
        min_hits: Minimum hit count threshold (default: 5)
        
    Returns:
        {
            "vehicle_id": "...",
            "gaps": [
                {
                    "surface_id": "spark_f",
                    "region_name": "high_map_midrange",
                    "rpm_range": [2500, 4500],
                    "map_range": [80, 100],
                    "empty_cells": 12,
                    "total_cells": 20,
                    "coverage_pct": 40.0,
                    "impact": "high",
                    "description": "..."
                },
                ...
            ]
        }
    """
    vehicle_id = request.args.get("vehicle_id", "default")
    min_hits = int(request.args.get("min_hits", 5))
    
    gaps = get_cumulative_gaps(vehicle_id, min_hits)
    
    return jsonify({
        "vehicle_id": vehicle_id,
        "gaps": gaps,
        "gap_count": len(gaps),
    }), 200


@nextgen_bp.route("/planner/constraints", methods=["GET"])
def get_constraints():
    """
    Get test planner constraints.
    
    Query Parameters:
        vehicle_id: Vehicle identifier (default: "default")
        
    Returns:
        {
            "min_rpm": 1000,
            "max_rpm": 7000,
            "min_map_kpa": 20,
            "max_map_kpa": 100,
            "max_pulls_per_session": 8,
            "preferred_test_environment": "both"
        }
    """
    vehicle_id = request.args.get("vehicle_id", "default")
    
    constraints = get_planner_constraints(vehicle_id)
    
    return jsonify(constraints.to_dict()), 200


@nextgen_bp.route("/planner/constraints", methods=["PUT"])
def update_constraints():
    """
    Update test planner constraints.
    
    Query Parameters:
        vehicle_id: Vehicle identifier (default: "default")
        
    Request Body:
        {
            "min_rpm": 1000,
            "max_rpm": 7000,
            "min_map_kpa": 20,
            "max_map_kpa": 100,
            "max_pulls_per_session": 8,
            "preferred_test_environment": "both"
        }
        
    Returns:
        {"success": true, "constraints": {...}}
    """
    vehicle_id = request.args.get("vehicle_id", "default")
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        constraints = TestPlannerConstraints.from_dict(data)
        success = save_planner_constraints(constraints, vehicle_id)
        
        if not success:
            return jsonify({"error": "Failed to save constraints"}), 500
        
        return jsonify({
            "success": True,
            "vehicle_id": vehicle_id,
            "constraints": constraints.to_dict(),
        }), 200
    except Exception as e:
        return jsonify({"error": f"Invalid constraints: {str(e)}"}), 400


@nextgen_bp.route("/planner/predict/<run_id>", methods=["POST"])
def predict_next_tests(run_id: str):
    """
    Get predictions for next tests based on cumulative coverage.
    
    URL Parameters:
        run_id: Current run ID (to extract vehicle_id or use "default")
        
    Query Parameters:
        vehicle_id: Vehicle identifier (default: "default")
        
    Returns:
        {
            "success": true,
            "vehicle_id": "...",
            "current_coverage_pct": 65.5,
            "recommended_tests": [
                {
                    "name": "High-MAP Midrange Pull",
                    "expected_coverage_gain": 8.5,
                    "efficiency_score": 0.85,
                    ...
                }
            ]
        }
    """
    run_id = secure_filename(run_id)
    vehicle_id = request.args.get("vehicle_id", "default")
    
    # Get cumulative coverage
    coverage = load_cumulative_coverage(vehicle_id)
    
    if coverage is None:
        return jsonify({
            "error": f"No coverage data found for vehicle {vehicle_id}",
            "vehicle_id": vehicle_id,
            "message": "Complete at least one run first",
        }), 404
    
    # Get coverage summary
    summary = get_coverage_summary(vehicle_id)
    current_coverage_pct = summary.get("coverage_pct", 0.0) if summary else 0.0
    
    # Get gaps
    gaps = get_cumulative_gaps(vehicle_id)
    
    # Get constraints
    constraints = get_planner_constraints(vehicle_id)
    
    # Load the current run to generate test plan
    workflow = get_nextgen_workflow()
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"Run {run_id} not found or not analyzed yet",
        }), 404
    
    # Extract test plan with efficiency scores
    next_tests = cached.get("next_tests", {})
    steps = next_tests.get("steps", [])
    
    # Filter steps by constraints
    filtered_steps = []
    for step in steps:
        # Check RPM constraints
        if step.get("rpm_range"):
            rpm_min, rpm_max = step["rpm_range"]
            if rpm_min < constraints.min_rpm or rpm_max > constraints.max_rpm:
                continue
        
        # Check MAP constraints
        if step.get("map_range"):
            map_min, map_max = step["map_range"]
            if map_min < constraints.min_map_kpa or map_max > constraints.max_map_kpa:
                continue
        
        # Check test environment preference
        test_type = step.get("test_type", "general")
        if constraints.preferred_test_environment == "inertia_dyno":
            if test_type not in ["wot_pull"]:
                continue
        elif constraints.preferred_test_environment == "street":
            if test_type == "wot_pull":
                continue
        
        filtered_steps.append(step)
    
    # Limit to max pulls per session
    if constraints.max_pulls_per_session:
        filtered_steps = filtered_steps[:constraints.max_pulls_per_session]
    
    return jsonify({
        "success": True,
        "vehicle_id": vehicle_id,
        "current_coverage_pct": current_coverage_pct,
        "total_runs": coverage.total_runs,
        "gaps": gaps[:5],  # Top 5 gaps
        "recommended_tests": filtered_steps,
        "constraints_applied": constraints.to_dict(),
    }), 200


@nextgen_bp.route("/planner/feedback", methods=["POST"])
def record_feedback():
    """
    Record run completion and update coverage tracker.
    
    Request Body:
        {
            "run_id": "...",
            "vehicle_id": "default",
            "dyno_signature": "..."
        }
        
    Returns:
        {
            "success": true,
            "vehicle_id": "...",
            "total_runs": 6,
            "new_coverage_pct": 75.2
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    run_id = data.get("run_id")
    vehicle_id = data.get("vehicle_id", "default")
    dyno_signature = data.get("dyno_signature", "unknown")
    
    if not run_id:
        return jsonify({"error": "run_id is required"}), 400
    
    # Load the run's surfaces
    workflow = get_nextgen_workflow()
    cached = workflow.load_cached(run_id)
    
    if cached is None:
        return jsonify({
            "error": f"Run {run_id} not found or not analyzed",
        }), 404
    
    surfaces = cached.get("surfaces", {})
    
    # Aggregate coverage
    updated_coverage = aggregate_run_coverage(
        vehicle_id=vehicle_id,
        run_id=run_id,
        surfaces=surfaces,
        dyno_signature=dyno_signature,
    )
    
    # Get new summary
    summary = get_coverage_summary(vehicle_id)
    new_coverage_pct = summary.get("coverage_pct", 0.0) if summary else 0.0
    
    return jsonify({
        "success": True,
        "vehicle_id": vehicle_id,
        "run_id": run_id,
        "total_runs": updated_coverage.total_runs,
        "new_coverage_pct": new_coverage_pct,
        "message": f"Coverage updated for vehicle {vehicle_id}",
    }), 200


@nextgen_bp.route("/planner/reset/<vehicle_id>", methods=["POST"])
def reset_coverage(vehicle_id: str):
    """
    Reset cumulative coverage for a vehicle.
    
    URL Parameters:
        vehicle_id: Vehicle identifier
        
    Returns:
        {"success": true, "message": "..."}
    """
    vehicle_id = secure_filename(vehicle_id)
    
    success = reset_cumulative_coverage(vehicle_id)
    
    if not success:
        return jsonify({"error": "Failed to reset coverage"}), 500
    
    return jsonify({
        "success": True,
        "vehicle_id": vehicle_id,
        "message": f"Coverage tracker reset for {vehicle_id}",
    }), 200

