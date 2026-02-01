# Agent Prompts: Closed-Loop Auto-Tune Debugging & Fixes

## 🔍 Diagnostic Prompt: Closed-Loop Auto-Tune Stuck at Iteration 0

**Context:** The Closed-Loop Auto-Tune feature shows "Iteration 0 / 10 (Running...)" with 5% progress and the message "Running first iteration... This takes 10-15 seconds (running full dyno pull + analysis). Progress will update when iteration 1 completes." However, it remains stuck at this state indefinitely.

**Diagnostic Investigation Prompt:**

```
The Closed-Loop Auto-Tune feature is stuck at iteration 0/10 with 5% progress and hasn't progressed after 60+ seconds. I need you to diagnose why the first iteration isn't completing.

Please investigate:

1. **Backend Thread Execution:**
   - Check if the background thread in `api/routes/virtual_tune.py` (lines 92-98) is actually starting and running
   - Verify the `orchestrator.run_session()` method is being called
   - Check if there are any exceptions being silently caught in the daemon thread

2. **Session Status Updates:**
   - Verify that `session.current_iteration` is being updated in `api/services/virtual_tuning_session.py` (line 303)
   - Check if the session status is transitioning from INITIALIZING → RUNNING
   - Confirm the status endpoint (`/api/virtual-tune/status/<session_id>`) is returning current data

3. **Iteration Execution:**
   - Check if `_run_iteration()` (line 343) is completing successfully
   - Verify the dyno simulator is running and returning data
   - Check if AFR analysis is completing
   - Look for any blocking operations or infinite loops

4. **Frontend Polling:**
   - Verify the React Query polling in `ClosedLoopTuningPanel.tsx` (lines 72-77) is working
   - Check if the 3-second refetch interval is triggering
   - Confirm the status endpoint is being called repeatedly

5. **Logging:**
   - Check backend logs for any errors or warnings
   - Look for the log message "Starting tuning session: {session_id}" (line 285)
   - Look for iteration start logs "Iteration {n}/{max}" (line 297)

Please provide:
- Root cause of the stuck iteration
- Specific code location where the issue occurs
- Recommended fix with code changes
- Any additional logging that should be added for better debugging
```

---

## 🔧 Fix Prompt 1: Add Exception Handling to Background Thread

**Use when:** Background thread is failing silently due to unhandled exceptions

```
The closed-loop auto-tune background thread is failing silently. Add proper exception handling and logging to the background thread in `api/routes/virtual_tune.py`.

Requirements:
1. Wrap the `orchestrator.run_session()` call in a try-except block
2. Log any exceptions with full stack traces
3. Update the session status to FAILED if an exception occurs
4. Store the error message in `session.error_message`
5. Ensure the session is still retrievable via the status endpoint after failure

The fix should be in the `/start` endpoint around lines 92-98 where the thread is created.
```

---

## 🔧 Fix Prompt 2: Add Progress Logging During First Iteration

**Use when:** Need better visibility into what's happening during the first iteration

```
Add detailed progress logging to the `_run_iteration()` method in `api/services/virtual_tuning_session.py` to help diagnose slow or stuck iterations.

Requirements:
1. Log when iteration starts (already exists at line 297)
2. Add log after Virtual ECU creation: "Virtual ECU created with VE tables"
3. Add log before dyno pull: "Starting dyno pull simulation..."
4. Add log after dyno pull: "Dyno pull complete, {n} data points captured"
5. Add log before AFR analysis: "Analyzing AFR errors..."
6. Add log after AFR analysis: "AFR analysis complete, max error: {error}"
7. Add log before VE correction calculation: "Calculating VE corrections..."
8. Add log at iteration completion: "Icons Iteration {n} complete in {duration}s"

All logs should use the existing logger at INFO level.
```

---

## 🔧 Fix Prompt 3: Add Timeout Protection to Iteration Execution

**Use when:** Iterations are hanging indefinitely due to blocking operations

```
Add timeout protection to prevent iterations from hanging indefinitely in the closed-loop tuning system.

Requirements:
1. Add a configurable `iteration_timeout_sec` parameter to `TuningSessionConfig` (default: 30 seconds)
2. Wrap the `_run_iteration()` call in `run_session()` with a timeout mechanism
3. If an iteration exceeds the timeout:
   - Log a warning: "⚠️ Iteration {n} exceeded timeout ({timeout}s)"
   - Mark the session as FAILED with error message "Iteration timeout"
   - Store partial results if available
4. Use `concurrent.futures.ThreadPoolExecutor` with timeout for clean implementation
5. Ensure the timeout doesn't leave the simulator in a bad state

Files to modify:
- `api/services/virtual_tuning_session.py` (TuningSessionConfig and run_session method)
```

---

## 🔧 Fix Prompt 4: Add Real-Time Progress Updates During Iteration

**Use when:** Users need more granular progress feedback during long iterations

```
The current implementation only shows progress after each iteration completes. Add real-time sub-iteration progress updates so users see activity during the 10-15 second first iteration.

Requirements:
1. Add a `progress_pct` field to `TuningSession` (0-100)
2. Update progress at key milestones in `_run_iteration()`:
   - 0%: Iteration started
   - 20%: Virtual ECU created
   - 40%: Dyno pull started
   - 70%: Dyno pull completed
   - 85%: AFR analysis completed
   - 100%: VE corrections calculated
3. Make progress updates thread-safe (use a lock)
4. Include progress in the status endpoint response
5. Update the frontend `ClosedLoopTuningPanel.tsx` to show sub-iteration progress

Files to modify:
- `api/services/virtual_tuning_session.py` (TuningSession class and _run_iteration method)
- `api/routes/virtual_tune.py` (status endpoint to include progress_pct)
- `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx` (display sub-iteration progress)
```

---

## 🔧 Fix Prompt 5: Add Health Check Endpoint for Debugging

**Use when:** Need a quick way to verify the virtual tuning system is operational

```
Add a health check endpoint to verify all components of the closed-loop tuning system are operational.

Requirements:
1. Create a new endpoint: `GET /api/virtual-tune/health`
2. Check the following components:
   - Orchestrator is initialized: `get_orchestrator()` succeeds
   - Dyno simulator can be instantiated: Create a test EngineProfile
   - Virtual ECU can be created: Create a test VirtualECU
   - AFR analysis is available: Import and verify `analyze_afr_errors` function
3. Return JSON with status for each component:
   ```json
   {
     "healthy": true,
     "components": {
       "orchestrator": "ok",
       "dyno_simulator": "ok",
       "virtual_ecu": "ok",
       "afr_analysis": "ok"
     },
     "timestamp": "2025-12-15T10:30:00Z"
   }
   ```
4. If any component fails, set `healthy: false` and include error details
5. Add a "Test Health" button to the frontend that calls this endpoint

Files to create/modify:
- `api/routes/virtual_tune.py` (add health endpoint)
- `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx` (add test button)
```

---

## 🔍 Diagnostic Prompt 2: Frontend Not Receiving Status Updates

**Use when:** Backend is working but frontend shows stale data

```
The closed-loop auto-tune backend appears to be running (check logs show iteration progress), but the frontend UI is stuck showing "Iteration 0 / 10" and not updating.

Please investigate:

1. **Network Requests:**
   - Open browser DevTools Network tab
   - Verify `GET /api/virtual-tune/status/{session_id}` requests are being made every 3 seconds
   - Check the response status codes (should be 200)
   - Inspect the response body - does it show current iteration data?

2. **React Query State:**
   - Check if `useQuery` in `ClosedLoopTuningPanel.tsx` (lines 63-77) is enabled
   - Verify `sessionId` is set correctly
   - Check if `refetchInterval` is returning 3000 (not false)
   - Look for React Query DevTools to see query state

3. **Component State:**
   - Verify `status` state variable is being updated when query data changes
   - Check if `progressPct` calculation (lines 143-147) is correct
   - Ensure the component is re-rendering when status changes

4. **CORS/API Issues:**
   - Verify API_BASE constant is correct: `http://127.0.0.1:5001/api/virtual-tune`
   - Check for CORS errors in browser console
   - Verify backend is running on port 5001

Please provide:
- Whether the issue is in data fetching or data rendering
- Specific component or query configuration that needs fixing
- Recommended code changes
```

---

## 🔧 Fix Prompt 6: Add Detailed Error Display in Frontend

**Use when:** Backend errors aren't being shown to users

```
Add comprehensive error display to the Closed-Loop Tuning Panel so users can see what went wrong when tuning fails.

Requirements:
1. Display `session.error_message` prominently when status is FAILED
2. Show a collapsible "Error Details" section with:
   - Session ID
   - Iteration where failure occurred
   - Full error message
   - Timestamp
3. Add a "View Backend Logs" button that links to log file location
4. Show network errors separately from backend errors
5. Add a "Retry" button that creates a new session with the same config
6. Use the Alert component with destructive variant for errors

Files to modify:
- `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx`

Example UI:
```
❌ FAILED
Tuning failed during iteration 2

[Error Details ▼]
  Session ID: tune_1234567890_5678
  Failed at: Iteration 2/10
  Error: Virtual ECU initialization failed: Invalid VE table dimensions
  Time: 2025-12-15 10:30:45

[View Backend Logs] [Retry Tuning]
```
```

---

## 🔧 Fix Prompt 7: Add Session Recovery After Page Refresh

**Use when:** Users lose progress when refreshing the page during tuning

```
Currently, if a user refreshes the page during closed-loop tuning, they lose visibility into the running session. Add session recovery.

Requirements:
1. Store the active session ID in localStorage when tuning starts
2. On component mount, check localStorage for an active session
3. If found, fetch the session status and resume monitoring
4. Clear localStorage when session completes or is manually stopped
5. Show a banner: "Resumed monitoring session from {time}"
6. Add a "Dismiss" option if the user wants to start a new session

Files to modify:
- `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx`

Implementation:
- Use `useEffect` on mount to check localStorage
- Key: `dynoai_active_tuning_session`
- Value: `{ sessionId: string, startTime: number }`
```

---

## 🔧 Fix Prompt 8: Add Iteration Timing Metrics

**Use when:** Need to understand performance bottlenecks in the tuning loop

```
Add detailed timing metrics to understand where time is spent during each iteration.

Requirements:
1. Add timing fields to `IterationResult`:
   - `duration_total_sec`: Total iteration time
   - `duration_ecu_creation_sec`: Time to create Virtual ECU
   - `duration_dyno_pull_sec`: Time for dyno simulation
   - `duration_afr_analysis_sec`: Time for AFR analysis
   - `duration_ve_calculation_sec`: Time to calculate corrections
2. Measure each phase using `time.time()` before/after
3. Log timing summary: "Iteration {n} timing: ECU={t1}s, Pull={t2}s, Analysis={t3}s, VE={t4}s, Total={t5}s"
4. Display timing in frontend iteration history
5. Add a "Performance" tab showing timing breakdown chart

Files to modify:
- `api/services/virtual_tuning_session.py` (IterationResult and _run_iteration)
- `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx` (display timing)
```

---

## 🔍 Diagnostic Prompt 3: Simulator Not Producing Data

**Use when:** Dyno simulator appears to be the bottleneck

```
The closed-loop tuning is stuck because the dyno simulator isn't producing data during the pull.

Please investigate:

1. **Simulator Initialization:**
   - Check if `DynoSimulator` is being created correctly in `_run_iteration()`
   - Verify the engine profile is valid
   - Check if Virtual ECU is being passed to the simulator

2. **Pull Execution:**
   - Check if `simulator.run_pull()` is being called
   - Verify pull parameters (RPM range, duration, etc.)
   - Look for any exceptions during pull execution

3. **Data Generation:**
   - Check if the physics engine is producing valid data
   - Verify AFR values are being calculated by Virtual ECU
   - Check if data points are being collected

4. **Dependencies:**
   - Verify all required imports are available
   - Check if numpy/scipy are installed and working
   - Look for any import errors in logs

5. **Simulator State:**
   - Check if simulator is in a valid state
   - Verify no previous runs left it in a bad state
   - Check for resource locks or conflicts

Please provide:
- Root cause of simulator failure
- Specific code location
- Recommended fix
- Any missing dependencies or configuration
```

---

## 🔧 Fix Prompt 9: Add Simulator State Reset Between Iterations

**Use when:** Simulator state is carrying over between iterations causing issues

```
Add proper state reset between iterations to ensure each iteration starts fresh.

Requirements:
1. Create a `reset()` method in the DynoSimulator class
2. Reset all state variables:
   - Current RPM
   - Throttle position
   - Engine heat state
   - Accumulated data
3. Call `reset()` at the start of each iteration
4. Add a similar `reset()` method to VirtualECU
5. Log state resets: "Simulator state reset for iteration {n}"
6. Add a test to verify reset works correctly

Files to modify:
- `api/services/dyno_simulator.py` (add reset method)
- `api/services/virtual_ecu.py` (add reset method)
- `api/services/virtual_tuning_session.py` (call reset in _run_iteration)
```

---

## 🔧 Fix Prompt 10: Add Cancellation Support for Long-Running Operations

**Use when:** Need to stop a stuck iteration without waiting for timeout

```
Add proper cancellation support so users can stop a stuck iteration immediately.

Requirements:
1. Add a cancellation flag to TuningSession: `cancel_requested: bool`
2. Check the flag at key points in `_run_iteration()`:
   - Before dyno pull
   - During dyno pull (in simulation loop)
   - Before AFR analysis
   - Before VE calculation
3. When cancellation is detected:
   - Stop current operation
   - Set status to STOPPED
   - Log: "Iteration cancelled by user request"
   - Return partial results if available
4. Add a "Cancel Current Iteration" button in frontend (in addition to "Stop" button)
5. Make the cancellation check thread-safe

Files to modify:
- `api/services/virtual_tuning_session.py` (add cancellation checks)
- `api/routes/virtual_tune.py` (add cancel endpoint)
- `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx` (add cancel button)
```

---

## 📋 Debugging Checklist Template

Use this checklist when investigating any closed-loop auto-tune issue:

```markdown
## Closed-Loop Auto-Tune Debugging Checklist

### Backend Health
- [ ] Flask server is running on port 5001
- [ ] Virtual tune blueprint is registered
- [ ] No import errors in logs
- [ ] Orchestrator initializes successfully

### Session Creation
- [ ] POST /api/virtual-tune/start returns 200
- [ ] Session ID is generated
- [ ] Background thread starts
- [ ] Session appears in orchestrator's session dict

### Iteration Execution
- [ ] Logs show "Starting tuning session: {id}"
- [ ] Logs show "Iteration 1/10"
- [ ] No exceptions in thread
- [ ] Dyno simulator runs successfully
- [ ] AFR analysis completes
- [ ] VE corrections are calculated

### Status Updates
- [ ] GET /api/virtual-tune/status/{id} returns 200
- [ ] Response shows current_iteration > 0
- [ ] Response includes iteration data
- [ ] Status transitions from RUNNING to CONVERGED/FAILED

### Frontend Polling
- [ ] Network tab shows status requests every 3s
- [ ] React Query is enabled
- [ ] sessionId is set correctly
- [ ] Component re-renders on data change

### UI Updates
- [ ] Progress bar advances
- [ ] Iteration counter updates
- [ ] Iteration history populates
- [ ] Convergence message appears

### Error Handling
- [ ] Errors are logged to backend
- [ ] Errors are returned in status response
- [ ] Frontend displays error messages
- [ ] Session can be stopped/reset after error
```

---

## 🎯 Quick Fix Priority Order

When debugging a stuck closed-loop auto-tune, apply fixes in this order:

1. **Fix Prompt 1**: Add exception handling to background thread (critical for visibility)
2. **Fix Prompt 2**: Add progress logging (helps identify where it's stuck)
3. **Diagnostic Prompt 1**: Run full diagnostic investigation
4. **Fix Prompt 3**: Add timeout protection (prevents indefinite hangs)
5. **Fix Prompt 4**: Add real-time progress updates (better UX)
6. **Fix Prompt 5**: Add health check endpoint (preventive debugging)

---

## 🔬 Advanced Diagnostic: Thread Inspection

**Use when:** Need to inspect the actual state of the background thread

```
Add thread inspection capabilities to diagnose stuck background threads.

Create a new endpoint: GET /api/virtual-tune/debug/threads

This endpoint should:
1. List all active threads
2. Show thread state (running, waiting, blocked)
3. Show thread stack trace if available
4. Identify the tuning session thread specifically
5. Show how long each thread has been running

Implementation:
- Use `threading.enumerate()` to list threads
- Use `sys._current_frames()` to get stack traces
- Store thread IDs when creating tuning threads
- Add thread name: `thread.name = f"tuning-{session_id}"`

This is for development/debugging only - add a flag to enable it.
```

---

## 📝 Logging Best Practices for Tuning System

When adding logging to diagnose issues:

1. **Use structured logging:**
   ```python
   logger.info(f"[Session:{session_id}] Iteration {n} started")
   ```

2. **Log timing information:**
   ```python
   start = time.time()
   # ... operation ...
   logger.info(f"Operation completed in {time.time() - start:.2f}s")
   ```

3. **Log state transitions:**
   ```python
   logger.info(f"Status: {old_status} → {new_status}")
   ```

4. **Log data shapes/sizes:**
   ```python
   logger.info(f"Captured {len(data)} data points, RPM range: {min_rpm}-{max_rpm}")
   ```

5. **Use appropriate log levels:**
   - DEBUG: Detailed internal state
   - INFO: Normal operation milestones
   - WARNING: Recoverable issues
   - ERROR: Failures that stop operation

---

## 🚀 Performance Optimization Prompts

### Optimize Prompt 1: Parallel Iteration Execution

```
Optimize the closed-loop tuning to run multiple iterations in parallel when possible.

Requirements:
1. Identify which iterations can run in parallel (they can't - each depends on previous)
2. Instead, parallelize within iteration:
   - Run front and rear cylinder AFR analysis in parallel
   - Calculate front and rear VE corrections in parallel
3. Use `concurrent.futures.ThreadPoolExecutor` for parallel tasks
4. Measure speedup and log it
5. Ensure thread safety for shared state

Expected improvement: 20-30% faster iterations
```

### Optimize Prompt 2: Cache Expensive Calculations

```
Add caching for expensive calculations that don't change between iterations.

Requirements:
1. Cache AFR target table (doesn't change between iterations)
2. Cache engine profile data
3. Cache barometric correction factors
4. Use `functools.lru_cache` where appropriate
5. Clear cache when session starts
6. Log cache hits/misses for monitoring

Expected improvement: 10-15% faster iterations
```

---

## 🧪 Testing Prompts

### Test Prompt 1: Add Integration Test for Full Tuning Session

```
Create a comprehensive integration test for the closed-loop tuning system.

Requirements:
1. Test file: `tests/integration/test_closed_loop_tuning.py`
2. Test a complete tuning session from start to finish
3. Verify:
   - Session is created
   - Iterations execute in order
   - Status updates correctly
   - Convergence is detected
   - Final VE tables are improved
4. Use a fast test profile (max 3 iterations)
5. Mock time-consuming operations if needed
6. Add assertions for timing (should complete in < 10s for test)
7. Test error cases (invalid config, simulator failure)

This test should run in CI/CD pipeline.
```

### Test Prompt 2: Add Frontend Component Test

```
Create a test for the ClosedLoopTuningPanel component.

Requirements:
1. Test file: `frontend/src/components/jetdrive/__tests__/ClosedLoopTuningPanel.test.tsx`
2. Use React Testing Library
3. Mock the API calls with MSW (Mock Service Worker)
4. Test scenarios:
   - Initial render
   - Starting a session
   - Progress updates
   - Convergence
   - Error handling
   - Stop button
5. Verify UI updates correctly for each state
6. Test accessibility (ARIA labels, keyboard navigation)

Use Jest and React Testing Library best practices.
```

---

## 🎓 Educational: Understanding the Tuning Flow

For anyone debugging the system, here's the complete flow:

```
1. User clicks "Start Closed-Loop Tuning"
   ↓
2. Frontend: POST /api/virtual-tune/start
   ↓
3. Backend: create_session() → Creates TuningSession
   ↓
4. Backend: Start background thread → run_session()
   ↓
5. Backend: Loop iterations (1 to max_iterations)
   ↓
6. Backend: _run_iteration()
   ├─ Create VirtualECU with current VE tables
   ├─ Create DynoSimulator with engine profile
   ├─ Run dyno pull (10-15 seconds)
   ├─ Analyze AFR errors
   ├─ Calculate VE corrections
   └─ Return IterationResult
   ↓
7. Backend: Update session.current_iteration
   ↓
8. Frontend: Poll GET /api/virtual-tune/status/{id} every 3s
   ↓
9. Frontend: Update UI with current iteration data
   ↓
10. Backend: Check convergence
    ├─ If converged → status = CONVERGED, exit loop
    ├─ If max iterations → status = MAX_ITERATIONS, exit loop
    └─ Else → apply corrections, next iteration
   ↓
11. Frontend: Show final results

Key timing:
- Session creation: < 1s
- First iteration: 10-15s (full dyno pull)
- Subsequent iterations: 8-12s
- Total for convergence (4 iterations): ~35-40s
```

---

## 🔑 Key Files Reference

Quick reference for where to look:

| Component | File | Key Lines |
|-----------|------|-----------|
| Frontend Panel | `frontend/src/components/jetdrive/ClosedLoopTuningPanel.tsx` | 53-352 |
| Status Polling | Same file | 63-77 |
| Progress Display | Same file | 143-147 |
| Backend Routes | `api/routes/virtual_tune.py` | 25-116 (start), 119-156 (status) |
| Background Thread | Same file | 92-98 |
| Orchestrator | `api/services/virtual_tuning_session.py` | 175-211 (class), 273-341 (run_session) |
| Iteration Logic | Same file | 343-450 (_run_iteration) |
| Session Model | Same file | 118-172 (TuningSession class) |
| Dyno Simulator | `api/services/dyno_simulator.py` | Full file |
| Virtual ECU | `api/services/virtual_ecu.py` | Full file |

---

## 💡 Common Root Causes & Solutions

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Stuck at iteration 0 | Thread exception | Fix Prompt 1 |
| Stuck at iteration 0 | Simulator hanging | Diagnostic Prompt 3 |
| Progress not updating | Frontend polling issue | Diagnostic Prompt 2 |
| Slow iterations | No optimization | Optimize Prompts 1-2 |
| Random failures | State not reset | Fix Prompt 9 |
| Can't stop | No cancellation | Fix Prompt 10 |
| Lost after refresh | No persistence | Fix Prompt 7 |
| Unclear errors | Poor error handling | Fix Prompt 6 |

---

## 🎯 Success Criteria

After applying fixes, verify:

- [ ] First iteration completes within 15 seconds
- [ ] Progress updates every 3 seconds
- [ ] All iterations complete successfully
- [ ] Convergence is detected correctly
- [ ] Errors are displayed clearly
- [ ] Stop button works immediately
- [ ] Session survives page refresh
- [ ] Backend logs show clear progress
- [ ] No silent failures
- [ ] Performance is acceptable (< 45s for 4 iterations)

