"""Jetstream progress SSE route for real-time updates."""

from flask import Blueprint, Response

from api.services.progress_broadcaster import get_broadcaster

progress_bp = Blueprint("jetstream_progress", __name__)


@progress_bp.route("/progress/<run_id>", methods=["GET"])
def stream_progress(run_id: str):
    """
    Stream progress events for a specific run using Server-Sent Events (SSE).

    Events:
        - connected: Initial connection confirmation
        - stage: Progress update with stage, substage, and percentage
        - complete: Run completed successfully
        - error: Run encountered an error

    Event data format:
        stage: {"run_id": "...", "stage": "processing", "substage": "binning", "progress": 45}
        complete: {"run_id": "...", "status": "complete", "results_summary": {...}}
        error: {"run_id": "...", "error": {"stage": "processing", "code": "E001", "message": "..."}}
    """
    broadcaster = get_broadcaster()

    def generate():
        for event in broadcaster.subscribe(run_id):
            yield event

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
