"""Jetstream progress SSE route for real-time updates."""

from flask import Blueprint, Response
from api.services.progress_broadcaster import get_broadcaster

progress_bp = Blueprint("jetstream_progress", __name__)


@progress_bp.route("/progress/<run_id>", methods=["GET"])
def stream_progress(run_id: str):
    """
    Stream progress updates.
    ---
    tags:
      - Jetstream
    summary: Stream progress events for a run using Server-Sent Events (SSE)
    description: |
      Establishes a Server-Sent Events (SSE) connection to receive real-time
      progress updates for a specific run.

      **Event Types:**
      - `connected`: Initial connection confirmation
      - `stage`: Progress update with stage, substage, and percentage
      - `complete`: Run completed successfully with results summary
      - `error`: Run encountered an error

      **Example Event Data:**
      ```
      event: stage
      data: {"run_id": "run_abc123", "stage": "processing", "substage": "binning", "progress": 45}

      event: complete
      data: {"run_id": "run_abc123", "status": "complete", "results_summary": {...}}
      ```
    produces:
      - text/event-stream
    parameters:
      - name: run_id
        in: path
        type: string
        required: true
        description: Unique run identifier to stream progress for
    responses:
      200:
        description: SSE stream established
        schema:
          type: string
          format: text/event-stream
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
