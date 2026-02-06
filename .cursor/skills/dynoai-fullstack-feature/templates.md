# Full-Stack Feature Templates

## Flask Blueprint (Extended)

For features with background processing (like analysis pipelines):

```python
"""<Feature> API routes with background processing."""
import logging
import threading
import uuid
from flask import Blueprint, jsonify, request

from api.errors import NotFoundError, ValidationError, with_error_handling

logger = logging.getLogger(__name__)

<feature>_bp = Blueprint("<feature>", __name__, url_prefix="/api/<feature>")

# In-memory session tracking (use DB for production persistence)
_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


@<feature>_bp.route("/start", methods=["POST"])
@with_error_handling
def start_session():
    """Start a new <feature> session."""
    data = request.get_json() or {}
    session_id = str(uuid.uuid4())[:8]

    with _sessions_lock:
        _sessions[session_id] = {
            "status": "running",
            "progress": 0,
            "result": None,
            "error": None,
        }

    thread = threading.Thread(
        target=_run_session,
        args=(session_id, data),
        daemon=True,
    )
    thread.start()

    return jsonify({"session_id": session_id, "status": "started"}), 202


@<feature>_bp.route("/status/<session_id>", methods=["GET"])
@with_error_handling
def get_session_status(session_id: str):
    """Get session status."""
    with _sessions_lock:
        session = _sessions.get(session_id)
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    return jsonify({"session_id": session_id, **session})


@<feature>_bp.route("/results/<session_id>", methods=["GET"])
@with_error_handling
def get_session_results(session_id: str):
    """Get session results."""
    with _sessions_lock:
        session = _sessions.get(session_id)
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if session["status"] != "complete":
        raise ValidationError(f"Session not complete (status: {session['status']})")
    return jsonify(session["result"])


def _run_session(session_id: str, data: dict):
    """Background session runner."""
    try:
        from api.services.<feature> import <Feature>Service
        result = <Feature>Service().analyze(data)
        with _sessions_lock:
            _sessions[session_id]["status"] = "complete"
            _sessions[session_id]["result"] = result
    except Exception as e:
        logger.error("Session %s failed: %s", session_id, e, exc_info=True)
        with _sessions_lock:
            _sessions[session_id]["status"] = "error"
            _sessions[session_id]["error"] = str(e)
```

## React Query Hook with Polling

For features that poll a background job:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import {
  start<Feature>Session,
  get<Feature>Status,
  get<Feature>Results,
  type <Feature>Session,
  type <Feature>Results,
} from "@/api/<feature>";

export function use<Feature>() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Poll status while session is running
  const {
    data: sessionStatus,
    isLoading: isLoadingStatus,
  } = useQuery({
    queryKey: ["<feature>", "status", sessionId],
    queryFn: () => get<Feature>Status(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "error") return false;
      return 2000; // Poll every 2s while running
    },
  });

  // Fetch results when complete
  const {
    data: results,
    isLoading: isLoadingResults,
  } = useQuery({
    queryKey: ["<feature>", "results", sessionId],
    queryFn: () => get<Feature>Results(sessionId!),
    enabled: !!sessionId && sessionStatus?.status === "complete",
    staleTime: Infinity,
  });

  const startMutation = useMutation({
    mutationFn: start<Feature>Session,
    onSuccess: (data) => {
      setSessionId(data.session_id);
    },
  });

  const start = useCallback(
    (params: Parameters<typeof start<Feature>Session>[0]) =>
      startMutation.mutateAsync(params),
    [startMutation]
  );

  const reset = useCallback(() => {
    setSessionId(null);
    queryClient.removeQueries({ queryKey: ["<feature>"] });
  }, [queryClient]);

  return {
    sessionId,
    sessionStatus,
    results,
    isStarting: startMutation.isPending,
    isRunning: sessionStatus?.status === "running",
    isComplete: sessionStatus?.status === "complete",
    isError: sessionStatus?.status === "error",
    isLoadingStatus,
    isLoadingResults,
    error: startMutation.error || sessionStatus?.error,
    start,
    reset,
  };
}
```

## API Client with Path Params

```typescript
import api from "@/lib/api";
import { encodePathSegment } from "@/lib/sanitize";

export interface <Feature>Session {
  session_id: string;
  status: "running" | "complete" | "error";
  progress: number;
  error?: string;
}

export interface <Feature>Results {
  status: string;
  results: Record<string, unknown>;
}

export async function start<Feature>Session(
  params: Record<string, unknown>
): Promise<{ session_id: string }> {
  const response = await api.post("/api/<feature>/start", params);
  return response.data;
}

export async function get<Feature>Status(
  sessionId: string
): Promise<<Feature>Session> {
  const response = await api.get(
    `/api/<feature>/status/${encodePathSegment(sessionId)}`
  );
  return response.data;
}

export async function get<Feature>Results(
  sessionId: string
): Promise<<Feature>Results> {
  const response = await api.get(
    `/api/<feature>/results/${encodePathSegment(sessionId)}`
  );
  return response.data;
}
```
