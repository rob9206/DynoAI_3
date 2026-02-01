# Agent Prompts: Async Operations & Progress Tracking Patterns

## 🎯 Purpose

This document provides reusable agent prompts for diagnosing and fixing common issues with:
- Long-running background operations
- Progress tracking and UI updates
- Polling mechanisms
- Thread/async execution
- Real-time data streaming

These patterns apply to any feature similar to the Closed-Loop Auto-Tune system.

---

## 📋 Pattern 1: Background Task Not Starting

### Diagnostic Prompt

```
I have a feature that starts a background task (thread/async/celery) but the task doesn't appear to be executing.

Feature details:
- Frontend component: [COMPONENT_PATH]
- Backend endpoint: [ENDPOINT_PATH]
- Background task location: [TASK_FUNCTION_PATH]

Please investigate:

1. **Task Initiation:**
   - Is the task creation code being reached?
   - Are there any exceptions during task creation?
   - Is the task ID/handle being returned correctly?

2. **Task Execution:**
   - Is the task function being called?
   - Are there any import errors or missing dependencies?
   - Is the task thread/process actually starting?

3. **Error Handling:**
   - Are exceptions being caught and logged?
   - Is there a try-except that's silently failing?
   - Are daemon threads exiting prematurely?

4. **Dependencies:**
   - Are all required services/resources available?
   - Are there any initialization failures?
   - Are there any blocking operations preventing start?

Please provide:
- Root cause of task not starting
- Specific code location
- Recommended fix with exception handling
- Logging additions for better visibility
```

### Fix Template

```
Add robust error handling and logging to the background task in [FILE_PATH].

Requirements:
1. Wrap task execution in try-except with full logging
2. Log task start: "Starting [TASK_NAME] with ID: {task_id}"
3. Log task completion: "[TASK_NAME] completed in {duration}s"
4. Log any exceptions with stack traces
5. Update task status to FAILED on exception
6. Ensure task status is queryable even after failure
7. Add a health check to verify task system is operational

Example pattern:
```python
def background_task(task_id: str, config: dict):
    logger.info(f"Starting {task_id}")
    start_time = time.time()
    
    try:
        # Update status to RUNNING
        task_manager.update_status(task_id, Status.RUNNING)
        
        # Execute task
        result = execute_task(config)
        
        # Update status to COMPLETED
        task_manager.update_status(task_id, Status.COMPLETED, result=result)
        
        duration = time.time() - start_time
        logger.info(f"Task {task_id} completed in {duration:.2f}s")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        task_manager.update_status(task_id, Status.FAILED, error=str(e))
        
    finally:
        # Cleanup resources
        cleanup_task_resources(task_id)
```
```

---

## 📋 Pattern 2: Progress Updates Not Reaching Frontend

### Diagnostic Prompt

```
My feature has a long-running operation with progress updates, but the frontend UI isn't showing progress changes.

Feature details:
- Frontend component: [COMPONENT_PATH]
- Backend status endpoint: [ENDPOINT_PATH]
- Progress update location: [PROGRESS_UPDATE_PATH]

Please investigate:

1. **Backend Progress Updates:**
   - Is progress being calculated and stored?
   - Is the progress value changing over time?
   - Is progress included in the status endpoint response?
   - Check the actual HTTP response body

2. **Frontend Polling:**
   - Is the polling mechanism active?
   - What is the poll interval?
   - Are HTTP requests being made repeatedly?
   - Check browser DevTools Network tab

3. **State Management:**
   - Is the React/Vue state being updated?
   - Is the component re-rendering on data change?
   - Are there any stale closures capturing old values?

4. **Data Flow:**
   - Trace the data from backend → network → frontend state → UI
   - Are there any transformations that might lose data?
   - Are field names consistent (camelCase vs snake_case)?

Please provide:
- Where the progress update flow is breaking
- Specific code location
- Recommended fix
- Any data transformation issues
```

### Fix Template

```
Fix the progress update flow for [FEATURE_NAME] to ensure frontend receives real-time updates.

Requirements:

**Backend (Python):**
1. Add thread-safe progress tracking:
```python
class TaskManager:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()
    
    def update_progress(self, task_id: str, progress_pct: float, message: str = ""):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].progress_pct = progress_pct
                self._tasks[task_id].progress_message = message
                self._tasks[task_id].last_update = time.time()
```

2. Include progress in status endpoint:
```python
@app.route("/api/task/<task_id>/status")
def get_task_status(task_id):
    task = task_manager.get_task(task_id)
    return jsonify({
        "task_id": task_id,
        "status": task.status,
        "progress_pct": task.progress_pct,  # 0-100
        "progress_message": task.progress_message,
        "current_step": task.current_step,
        "total_steps": task.total_steps
    })
```

**Frontend (React/TypeScript):**
1. Set up polling with React Query:
```typescript
const { data: status } = useQuery({
  queryKey: ['task-status', taskId],
  queryFn: async () => {
    const res = await fetch(`/api/task/${taskId}/status`);
    return res.json();
  },
  enabled: !!taskId,
  refetchInterval: (data) => {
    // Poll every 1s while running
    if (data?.status === 'running') return 1000;
    return false; // Stop when complete
  }
});
```

2. Display progress:
```typescript
<Progress value={status?.progress_pct || 0} />
<p className="text-sm text-muted-foreground">
  {status?.progress_message}
</p>
```

3. Add debug logging:
```typescript
useEffect(() => {
  console.log('[TaskProgress] Status update:', status);
}, [status]);
```
```

---

## 📋 Pattern 3: Polling Stops Prematurely

### Diagnostic Prompt

```
My frontend polling mechanism stops before the background task completes.

Feature details:
- Polling implementation: [FILE_PATH and LINE_NUMBERS]
- Expected poll duration: [DURATION]
- Actual behavior: [DESCRIPTION]

Please investigate:

1. **Polling Configuration:**
   - What is the refetchInterval logic?
   - Under what conditions does polling stop?
   - Is there a maximum poll count or timeout?

2. **Status Conditions:**
   - What status values trigger polling to continue?
   - What status values stop polling?
   - Is the backend returning unexpected status values?

3. **Component Lifecycle:**
   - Does the component unmount during polling?
   - Are there any navigation events that stop polling?
   - Is the query being disabled unexpectedly?

4. **React Query State:**
   - Is the query key changing (causing restart)?
   - Is the query being garbage collected?
   - Are there any stale time or cache time issues?

Please provide:
- Why polling is stopping
- Specific code location
- Recommended fix
- Any edge cases to handle
```

### Fix Template

```
Fix the polling mechanism for [FEATURE_NAME] to continue until task completion.

Requirements:

1. **Robust refetchInterval logic:**
```typescript
const { data: status } = useQuery({
  queryKey: ['task-status', taskId],
  queryFn: fetchStatus,
  enabled: !!taskId && !isComplete,
  refetchInterval: (data) => {
    // Continue polling for these statuses
    const activeStatuses = ['pending', 'running', 'initializing'];
    
    if (data?.status && activeStatuses.includes(data.status)) {
      return 1000; // Poll every 1s
    }
    
    // Stop polling for terminal statuses
    const terminalStatuses = ['completed', 'failed', 'cancelled'];
    if (data?.status && terminalStatuses.includes(data.status)) {
      return false;
    }
    
    // Default: keep polling if we're not sure
    return 2000;
  },
  refetchIntervalInBackground: false, // Stop when tab is hidden
  staleTime: 0, // Always fetch fresh data
});
```

2. **Add polling state tracking:**
```typescript
const [pollingActive, setPollingActive] = useState(false);

useEffect(() => {
  if (status?.status === 'running') {
    setPollingActive(true);
  } else if (['completed', 'failed'].includes(status?.status)) {
    setPollingActive(false);
  }
}, [status]);

// Debug logging
useEffect(() => {
  console.log('[Polling]', {
    active: pollingActive,
    status: status?.status,
    taskId,
    timestamp: new Date().toISOString()
  });
}, [pollingActive, status, taskId]);
```

3. **Add manual refresh button:**
```typescript
const { refetch } = useQuery(/* ... */);

<Button onClick={() => refetch()}>
  <RefreshCw className="h-4 w-4 mr-2" />
  Refresh Status
</Button>
```

4. **Add timeout protection:**
```typescript
const [startTime] = useState(Date.now());
const TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

useEffect(() => {
  if (status?.status === 'running') {
    const elapsed = Date.now() - startTime;
    if (elapsed > TIMEOUT_MS) {
      toast.error('Task timeout - please check backend logs');
      // Optionally stop polling or show error UI
    }
  }
}, [status, startTime]);
```
```

---

## 📋 Pattern 4: Thread Safety Issues in Progress Updates

### Diagnostic Prompt

```
My background task updates progress from multiple threads/locations, and I'm seeing race conditions or inconsistent values.

Feature details:
- Task implementation: [FILE_PATH]
- Number of threads/workers: [COUNT]
- Progress update locations: [LIST_OF_LOCATIONS]

Please investigate:

1. **Concurrent Access:**
   - Are multiple threads updating the same progress variable?
   - Is there any locking mechanism in place?
   - Are updates atomic?

2. **Data Consistency:**
   - Can progress go backwards?
   - Are there any race conditions in read-modify-write operations?
   - Is progress calculation based on shared state?

3. **Update Frequency:**
   - How often is progress being updated?
   - Could rapid updates cause issues?
   - Is there any throttling or debouncing?

Please provide:
- Thread safety issues identified
- Recommended locking strategy
- Code changes needed
```

### Fix Template

```
Add thread-safe progress tracking to [FEATURE_NAME].

Requirements:

1. **Thread-safe progress manager:**
```python
import threading
from dataclasses import dataclass
from typing import Optional

@dataclass
class TaskProgress:
    task_id: str
    progress_pct: float = 0.0
    current_step: int = 0
    total_steps: int = 0
    message: str = ""
    last_update: float = 0.0

class ThreadSafeProgressTracker:
    def __init__(self):
        self._progress: dict[str, TaskProgress] = {}
        self._lock = threading.Lock()
    
    def update(
        self,
        task_id: str,
        progress_pct: Optional[float] = None,
        current_step: Optional[int] = None,
        message: Optional[str] = None
    ):
        with self._lock:
            if task_id not in self._progress:
                self._progress[task_id] = TaskProgress(task_id=task_id)
            
            prog = self._progress[task_id]
            
            if progress_pct is not None:
                prog.progress_pct = max(0, min(100, progress_pct))
            
            if current_step is not None:
                prog.current_step = current_step
                if prog.total_steps > 0:
                    prog.progress_pct = (current_step / prog.total_steps) * 100
            
            if message is not None:
                prog.message = message
            
            prog.last_update = time.time()
    
    def get(self, task_id: str) -> Optional[TaskProgress]:
        with self._lock:
            return self._progress.get(task_id)
    
    def increment(self, task_id: str, delta: float = 1.0):
        """Atomically increment progress"""
        with self._lock:
            if task_id in self._progress:
                self._progress[task_id].progress_pct += delta
                self._progress[task_id].progress_pct = min(100, self._progress[task_id].progress_pct)

# Global instance
progress_tracker = ThreadSafeProgressTracker()
```

2. **Use in background task:**
```python
def background_task(task_id: str):
    progress_tracker.update(task_id, progress_pct=0, message="Starting...")
    
    # Step 1
    progress_tracker.update(task_id, progress_pct=20, message="Loading data...")
    load_data()
    
    # Step 2
    progress_tracker.update(task_id, progress_pct=50, message="Processing...")
    process_data()
    
    # Step 3
    progress_tracker.update(task_id, progress_pct=80, message="Finalizing...")
    finalize()
    
    progress_tracker.update(task_id, progress_pct=100, message="Complete!")
```

3. **Expose in API:**
```python
@app.route("/api/task/<task_id>/progress")
def get_progress(task_id):
    progress = progress_tracker.get(task_id)
    if not progress:
        return jsonify({"error": "Task not found"}), 404
    
    return jsonify({
        "task_id": progress.task_id,
        "progress_pct": progress.progress_pct,
        "current_step": progress.current_step,
        "total_steps": progress.total_steps,
        "message": progress.message,
        "last_update": progress.last_update
    })
```
```

---

## 📋 Pattern 5: Memory Leaks in Long-Running Tasks

### Diagnostic Prompt

```
My background tasks are accumulating in memory and not being cleaned up after completion.

Feature details:
- Task storage: [STORAGE_MECHANISM]
- Expected task lifetime: [DURATION]
- Observed behavior: [DESCRIPTION]

Please investigate:

1. **Task Lifecycle:**
   - Are completed tasks being removed from storage?
   - Is there a cleanup mechanism?
   - Are there any references preventing garbage collection?

2. **Resource Management:**
   - Are file handles being closed?
   - Are network connections being cleaned up?
   - Are large data structures being released?

3. **Storage Size:**
   - How many tasks are stored in memory?
   - Is there a maximum size limit?
   - Is there any automatic expiration?

Please provide:
- Memory leak sources
- Cleanup strategy
- Code changes needed
```

### Fix Template

```
Add automatic cleanup and memory management for [FEATURE_NAME] background tasks.

Requirements:

1. **Task expiration:**
```python
from datetime import datetime, timedelta
from typing import Dict
import threading

class TaskManager:
    def __init__(self, max_age_minutes: int = 60, max_tasks: int = 100):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._max_age = timedelta(minutes=max_age_minutes)
        self._max_tasks = max_tasks
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
    
    def _cleanup_loop(self):
        """Periodically clean up old tasks"""
        while True:
            time.sleep(300)  # Run every 5 minutes
            self._cleanup_old_tasks()
    
    def _cleanup_old_tasks(self):
        """Remove tasks older than max_age"""
        with self._lock:
            now = datetime.now()
            expired = [
                task_id
                for task_id, task in self._tasks.items()
                if task.end_time and (now - task.end_time) > self._max_age
            ]
            
            for task_id in expired:
                logger.info(f"Cleaning up expired task: {task_id}")
                self._cleanup_task_resources(task_id)
                del self._tasks[task_id]
            
            # Also enforce max task limit
            if len(self._tasks) > self._max_tasks:
                # Remove oldest completed tasks
                completed = [
                    (task_id, task)
                    for task_id, task in self._tasks.items()
                    if task.status in ['completed', 'failed', 'cancelled']
                ]
                completed.sort(key=lambda x: x[1].end_time or datetime.min)
                
                to_remove = len(self._tasks) - self._max_tasks
                for task_id, _ in completed[:to_remove]:
                    logger.info(f"Removing old task (limit): {task_id}")
                    self._cleanup_task_resources(task_id)
                    del self._tasks[task_id]
    
    def _cleanup_task_resources(self, task_id: str):
        """Clean up any resources associated with task"""
        task = self._tasks.get(task_id)
        if not task:
            return
        
        # Close any open files
        if hasattr(task, 'file_handles'):
            for fh in task.file_handles:
                try:
                    fh.close()
                except:
                    pass
        
        # Clear large data structures
        if hasattr(task, 'data'):
            task.data = None
        
        # Cancel any pending operations
        if hasattr(task, 'cancel'):
            task.cancel()
```

2. **Manual cleanup endpoint:**
```python
@app.route("/api/tasks/cleanup", methods=["POST"])
def cleanup_tasks():
    """Manually trigger task cleanup"""
    data = request.get_json() or {}
    
    # Clean up specific task
    if task_id := data.get("task_id"):
        task_manager.remove_task(task_id)
        return jsonify({"success": True, "removed": [task_id]})
    
    # Clean up all completed tasks
    if data.get("all_completed"):
        removed = task_manager.cleanup_completed()
        return jsonify({"success": True, "removed": removed})
    
    # Clean up old tasks
    removed = task_manager.cleanup_old_tasks()
    return jsonify({"success": True, "removed": removed})
```

3. **Add cleanup on task completion:**
```python
def background_task(task_id: str):
    try:
        # Task execution
        result = execute_task()
        task_manager.complete_task(task_id, result)
    except Exception as e:
        task_manager.fail_task(task_id, str(e))
    finally:
        # Schedule cleanup after 1 hour
        threading.Timer(
            3600,
            lambda: task_manager.remove_task(task_id)
        ).start()
```
```

---

## 📋 Pattern 6: Real-Time Data Streaming Issues

### Diagnostic Prompt

```
My feature streams real-time data to the frontend, but data is delayed, choppy, or missing.

Feature details:
- Streaming mechanism: [SSE/WebSocket/Polling]
- Expected update frequency: [FREQUENCY]
- Observed behavior: [DESCRIPTION]

Please investigate:

1. **Data Generation:**
   - Is data being generated at the expected rate?
   - Are there any bottlenecks in data production?
   - Is data being buffered somewhere?

2. **Transport:**
   - Is the connection stable?
   - Are there any network issues?
   - Is data being throttled or rate-limited?

3. **Frontend Processing:**
   - Is the frontend keeping up with data rate?
   - Are there any rendering performance issues?
   - Is data being queued or dropped?

4. **Synchronization:**
   - Are timestamps correct?
   - Is there clock drift between client/server?
   - Are updates arriving in order?

Please provide:
- Root cause of streaming issues
- Recommended improvements
- Code changes needed
```

### Fix Template

```
Optimize real-time data streaming for [FEATURE_NAME].

Requirements:

1. **Backend: Efficient data generation**
```python
from collections import deque
import time

class DataStreamer:
    def __init__(self, max_buffer_size: int = 1000):
        self._buffer = deque(maxlen=max_buffer_size)
        self._lock = threading.Lock()
        self._subscribers = []
    
    def add_data(self, data: dict):
        """Add data point (called by data source)"""
        with self._lock:
            data['timestamp'] = time.time()
            self._buffer.append(data)
    
    def get_latest(self, count: int = 1) -> list:
        """Get latest N data points"""
        with self._lock:
            return list(self._buffer)[-count:]
    
    def get_since(self, timestamp: float) -> list:
        """Get all data since timestamp"""
        with self._lock:
            return [d for d in self._buffer if d['timestamp'] > timestamp]
```

2. **Polling endpoint with delta updates:**
```python
@app.route("/api/stream/<stream_id>/data")
def get_stream_data(stream_id: str):
    """Get data since last poll"""
    since = float(request.args.get('since', 0))
    
    streamer = get_streamer(stream_id)
    if not streamer:
        return jsonify({"error": "Stream not found"}), 404
    
    # Get only new data since last poll
    data = streamer.get_since(since)
    
    return jsonify({
        "stream_id": stream_id,
        "data": data,
        "count": len(data),
        "latest_timestamp": data[-1]['timestamp'] if data else since,
        "server_time": time.time()
    })
```

3. **Frontend: Efficient polling with delta updates**
```typescript
const [lastTimestamp, setLastTimestamp] = useState(0);
const [dataPoints, setDataPoints] = useState<DataPoint[]>([]);

const { data: streamData } = useQuery({
  queryKey: ['stream-data', streamId, lastTimestamp],
  queryFn: async () => {
    const res = await fetch(
      `/api/stream/${streamId}/data?since=${lastTimestamp}`
    );
    return res.json();
  },
  enabled: !!streamId && isStreaming,
  refetchInterval: 100, // Poll every 100ms for real-time feel
  onSuccess: (data) => {
    if (data.data.length > 0) {
      // Append new data points
      setDataPoints(prev => {
        const combined = [...prev, ...data.data];
        // Keep only last 1000 points
        return combined.slice(-1000);
      });
      
      // Update timestamp for next poll
      setLastTimestamp(data.latest_timestamp);
    }
  }
});
```

4. **Add performance monitoring:**
```typescript
const [stats, setStats] = useState({
  dataRate: 0,
  avgLatency: 0,
  droppedFrames: 0
});

useEffect(() => {
  const interval = setInterval(() => {
    const now = Date.now();
    const recentData = dataPoints.filter(
      d => (now - d.timestamp * 1000) < 1000
    );
    
    setStats({
      dataRate: recentData.length, // points per second
      avgLatency: calculateAvgLatency(recentData),
      droppedFrames: calculateDroppedFrames(recentData)
    });
  }, 1000);
  
  return () => clearInterval(interval);
}, [dataPoints]);

// Display stats in dev mode
{process.env.NODE_ENV === 'development' && (
  <div className="text-xs text-muted-foreground">
    {stats.dataRate} pts/s | {stats.avgLatency}ms latency
  </div>
)}
```
```

---

## 📋 Pattern 7: Inconsistent State After Errors

### Diagnostic Prompt

```
After an error occurs in my background task, the system is left in an inconsistent state.

Feature details:
- Task implementation: [FILE_PATH]
- Error scenario: [DESCRIPTION]
- Inconsistent state: [WHAT'S WRONG]

Please investigate:

1. **Error Handling:**
   - Are all exceptions being caught?
   - Is cleanup happening in finally blocks?
   - Are partial results being saved?

2. **State Management:**
   - What state changes before the error?
   - Is state being rolled back on error?
   - Are there any orphaned resources?

3. **Recovery:**
   - Can the task be retried?
   - Is manual intervention required?
   - Can the system self-heal?

Please provide:
- State consistency issues
- Rollback strategy
- Code changes needed
```

### Fix Template

```
Add transactional semantics and proper error recovery to [FEATURE_NAME].

Requirements:

1. **Implement state snapshots:**
```python
from copy import deepcopy
from contextlib import contextmanager

class StatefulTask:
    def __init__(self):
        self.state = {}
        self._state_history = []
    
    @contextmanager
    def transaction(self, description: str = ""):
        """Context manager for transactional state changes"""
        # Save current state
        snapshot = deepcopy(self.state)
        self._state_history.append((description, snapshot))
        
        try:
            yield self.state
            # Commit: keep changes
            logger.info(f"Transaction committed: {description}")
        except Exception as e:
            # Rollback: restore snapshot
            logger.warning(f"Transaction rolled back: {description} - {e}")
            self.state = snapshot
            raise
        finally:
            # Cleanup
            if len(self._state_history) > 10:
                self._state_history.pop(0)
    
    def rollback_to_snapshot(self, index: int = -1):
        """Manually rollback to a previous state"""
        if self._state_history:
            description, snapshot = self._state_history[index]
            self.state = deepcopy(snapshot)
            logger.info(f"Rolled back to: {description}")
```

2. **Use transactions in task:**
```python
def background_task(task_id: str):
    task = StatefulTask()
    
    try:
        # Phase 1: Load data
        with task.transaction("load_data"):
            task.state['data'] = load_data()
            task.state['data_loaded'] = True
        
        # Phase 2: Process
        with task.transaction("process_data"):
            task.state['result'] = process(task.state['data'])
            task.state['processed'] = True
        
        # Phase 3: Save
        with task.transaction("save_result"):
            save_result(task.state['result'])
            task.state['saved'] = True
        
        return task.state['result']
        
    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        
        # Try to save partial results
        try:
            save_partial_results(task.state)
        except:
            pass
        
        # Update task status
        task_manager.fail_task(task_id, str(e), partial_state=task.state)
        
        raise
```

3. **Add recovery endpoint:**
```python
@app.route("/api/task/<task_id>/recover", methods=["POST"])
def recover_task(task_id: str):
    """Attempt to recover a failed task"""
    task = task_manager.get_task(task_id)
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    if task.status != 'failed':
        return jsonify({"error": "Task is not in failed state"}), 400
    
    try:
        # Try to resume from partial state
        if task.partial_state:
            result = resume_task(task_id, task.partial_state)
            task_manager.complete_task(task_id, result)
            return jsonify({"success": True, "recovered": True})
        else:
            # Restart from beginning
            new_task_id = restart_task(task.config)
            return jsonify({
                "success": True,
                "recovered": False,
                "new_task_id": new_task_id
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```
```

---

## 📋 Quick Reference: Common Patterns

| Issue | Pattern | Fix Prompt |
|-------|---------|-----------|
| Task not starting | Pattern 1 | Background Task Not Starting |
| Progress not updating | Pattern 2 | Progress Updates Not Reaching Frontend |
| Polling stops early | Pattern 3 | Polling Stops Prematurely |
| Race conditions | Pattern 4 | Thread Safety Issues |
| Memory leaks | Pattern 5 | Memory Leaks in Long-Running Tasks |
| Choppy streaming | Pattern 6 | Real-Time Data Streaming Issues |
| Inconsistent state | Pattern 7 | Inconsistent State After Errors |

---

## 🎯 Debugging Workflow

When facing any async/progress tracking issue:

1. **Identify the pattern** - Which of the 7 patterns does this match?
2. **Run diagnostic prompt** - Get a comprehensive analysis
3. **Apply fix template** - Implement the recommended solution
4. **Add logging** - Ensure visibility for future debugging
5. **Test edge cases** - Verify error handling and recovery
6. **Document** - Add comments explaining the async behavior

---

## 🧪 Testing Checklist for Async Features

- [ ] Task starts successfully
- [ ] Progress updates reach frontend
- [ ] Polling continues until completion
- [ ] Thread-safe concurrent access
- [ ] No memory leaks after many tasks
- [ ] Real-time data arrives promptly
- [ ] Errors leave system in consistent state
- [ ] Tasks can be stopped/cancelled
- [ ] Tasks can be recovered after failure
- [ ] System handles high load gracefully
- [ ] Timeouts work correctly
- [ ] Cleanup happens automatically
- [ ] Frontend survives page refresh
- [ ] Backend survives server restart

---

## 💡 Best Practices

### Backend (Python/Flask)

1. **Always use locks for shared state:**
   ```python
   self._lock = threading.Lock()
   with self._lock:
       # Modify shared state
   ```

2. **Log at key points:**
   ```python
   logger.info(f"[{task_id}] Phase started: {phase_name}")
   ```

3. **Use daemon=True for background threads:**
   ```python
   thread = threading.Thread(target=task, daemon=True)
   ```

4. **Implement cleanup in finally blocks:**
   ```python
   try:
       execute_task()
   finally:
       cleanup_resources()
   ```

5. **Store task state for debugging:**
   ```python
   task.debug_info = {
       'start_time': start_time,
       'last_checkpoint': checkpoint,
       'thread_id': threading.get_ident()
   }
   ```

### Frontend (React/TypeScript)

1. **Use React Query for polling:**
   ```typescript
   const { data } = useQuery({
     queryKey: ['task', taskId],
     queryFn: fetchTask,
     refetchInterval: 1000
   });
   ```

2. **Handle loading states:**
   ```typescript
   if (isLoading) return <Spinner />;
   if (error) return <ErrorDisplay error={error} />;
   ```

3. **Debounce rapid updates:**
   ```typescript
   const debouncedProgress = useDebounce(progress, 100);
   ```

4. **Clean up on unmount:**
   ```typescript
   useEffect(() => {
     return () => {
       // Cleanup
     };
   }, []);
   ```

5. **Add debug logging:**
   ```typescript
   useEffect(() => {
     console.log('[Component] State:', { status, progress });
   }, [status, progress]);
   ```

---

## 🔗 Related Documents

- `AGENT_PROMPTS_CLOSED_LOOP_DEBUGGING.md` - Specific prompts for closed-loop tuning
- `VIRTUAL_TUNING_QUICK_REFERENCE.md` - User guide for virtual tuning
- `TROUBLESHOOTING_VIRTUAL_TUNING.md` - User-facing troubleshooting

---

## 📝 Contributing New Patterns

When you encounter a new async/progress tracking pattern:

1. Document the issue clearly
2. Create a diagnostic prompt
3. Create a fix template
4. Add to the quick reference table
5. Include testing checklist items
6. Add best practices if applicable

Keep this document as a living reference for all async operation patterns in the codebase.

