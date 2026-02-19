# Agent Prompts Library - Index

## 📚 Overview

This library contains comprehensive diagnostic and fix prompts for debugging common issues in the DynoAI codebase. These prompts are designed to be used with AI coding assistants to quickly identify and resolve problems.

---

## 📖 Available Documents

### 1. [AGENT_PROMPTS_CLOSED_LOOP_DEBUGGING.md](./AGENT_PROMPTS_CLOSED_LOOP_DEBUGGING.md)
**Purpose:** Specific prompts for the Closed-Loop Auto-Tune feature

**Contents:**
- Diagnostic prompt for stuck iterations
- 10 fix prompts for common issues
- Debugging checklist
- Performance optimization prompts
- Testing prompts
- Complete flow documentation

**Use when:**
- Closed-loop tuning isn't starting
- Progress stuck at iteration 0
- Iterations taking too long
- Frontend not updating
- Need to add timeout protection
- Want to optimize performance

**Key Prompts:**
1. Main diagnostic: "Closed-Loop Auto-Tune Stuck at Iteration 0"
2. Fix 1: Add exception handling to background thread
3. Fix 2: Add progress logging
4. Fix 3: Add timeout protection
5. Fix 4: Add real-time progress updates
6. Fix 5: Add health check endpoint

---

### 2. [AGENT_PROMPTS_ASYNC_PROGRESS_PATTERNS.md](./AGENT_PROMPTS_ASYNC_PROGRESS_PATTERNS.md)
**Purpose:** Reusable patterns for any async operation with progress tracking

**Contents:**
- 7 common patterns with diagnostic + fix prompts
- Thread safety patterns
- Memory leak prevention
- Real-time streaming patterns
- State consistency patterns
- Testing checklists
- Best practices

**Use when:**
- Any background task not starting
- Progress updates not reaching frontend
- Polling stops prematurely
- Race conditions in progress updates
- Memory leaks from long-running tasks
- Choppy real-time data streaming
- Inconsistent state after errors

**Key Patterns:**
1. Background Task Not Starting
2. Progress Updates Not Reaching Frontend
3. Polling Stops Prematurely
4. Thread Safety Issues
5. Memory Leaks in Long-Running Tasks
6. Real-Time Data Streaming Issues
7. Inconsistent State After Errors

---

### 3. [AGENT_PROMPTS_JETDRIVE_REALTIME_FEATURES.md](./AGENT_PROMPTS_JETDRIVE_REALTIME_FEATURES.md)
**Purpose:** Specific prompts for JetDrive hardware integration and real-time features

**Contents:**
- Live data capture diagnostics
- Auto-detection debugging
- VE table update optimization
- Session replay implementation
- Hardware communication reliability
- Channel name mapping
- Testing checklist

**Use when:**
- Live data not updating from dyno
- Auto-detect not triggering on runs
- VE table not highlighting cells
- Session replay not playing
- Hardware connection timeouts
- Channel name mismatches
- Need to optimize real-time performance

**Key Prompts:**
1. Live Data Not Updating
2. Quick Tune Not Auto-Detecting Runs
3. VE Table Not Updating in Real-Time
4. Session Replay Not Playing Back
5. Hardware Communication Timeout

---

## 🎯 Quick Start Guide

### Step 1: Identify Your Issue Category

| Your Issue | Use This Document |
|------------|-------------------|
| Closed-loop tuning stuck/slow | CLOSED_LOOP_DEBUGGING |
| Any background task issue | ASYNC_PROGRESS_PATTERNS |
| JetDrive/hardware issue | JETDRIVE_REALTIME_FEATURES |
| General async/progress issue | ASYNC_PROGRESS_PATTERNS |
| Real-time data streaming | JETDRIVE_REALTIME_FEATURES or ASYNC_PROGRESS_PATTERNS |

### Step 2: Find the Right Prompt

Each document has:
- **Diagnostic Prompts** (🔍) - To understand what's wrong
- **Fix Prompts** (🔧) - To implement solutions
- **Quick Reference Tables** - To find prompts fast

### Step 3: Use the Prompt

1. Copy the entire prompt text
2. Provide it to your AI coding assistant
3. Add any specific details about your situation
4. Review the analysis and recommendations
5. Implement the suggested fixes

### Step 4: Verify the Fix

Each document includes:
- Testing checklists
- Success criteria
- Debugging workflows

---

## 🔄 Common Workflows

### Workflow 1: Debugging a Stuck Background Task

```
1. Open: ASYNC_PROGRESS_PATTERNS.md
2. Use: Pattern 1 - "Background Task Not Starting"
3. Run diagnostic prompt
4. Apply fix template
5. Verify with testing checklist
```

### Workflow 2: Fixing Closed-Loop Tuning

```
1. Open: AGENT_PROMPTS_CLOSED_LOOP_DEBUGGING.md
2. Use: Main diagnostic prompt
3. Based on findings, apply Fix Prompts 1-3
4. Add logging (Fix Prompt 2)
5. Test with the debugging checklist
```

### Workflow 3: Optimizing Real-Time Data

```
1. Open: AGENT_PROMPTS_JETDRIVE_REALTIME_FEATURES.md
2. Use: "Live Data Not Updating" diagnostic
3. Apply: "Channel Name Mapping Debug" fix
4. Open: ASYNC_PROGRESS_PATTERNS.md
5. Use: Pattern 6 - "Real-Time Data Streaming"
6. Optimize with streaming patterns
```

### Workflow 4: Adding New Async Feature

```
1. Open: ASYNC_PROGRESS_PATTERNS.md
2. Review: Best Practices section
3. Use: Testing Checklist for Async Features
4. Implement using patterns as templates
5. Add feature-specific prompts to this library
```

---

## 📊 Prompt Categories

### Diagnostic Prompts (🔍)
**Purpose:** Understand what's wrong

**Characteristics:**
- Ask comprehensive questions
- Check multiple potential causes
- Request specific information
- Provide structured investigation steps

**When to use:**
- Issue is unclear
- Multiple possible causes
- Need systematic investigation
- Want to understand root cause

**Example:**
> "Please investigate: 1. Backend Thread Execution... 2. Session Status Updates... 3. Iteration Execution..."

---

### Fix Prompts (🔧)
**Purpose:** Implement solutions

**Characteristics:**
- Provide specific requirements
- Include code templates
- Show best practices
- List files to modify

**When to use:**
- Root cause is known
- Ready to implement fix
- Need code examples
- Want to follow best practices

**Example:**
> "Add robust error handling... Requirements: 1. Wrap task execution... 2. Log task start... 3. Update status..."

---

### Optimization Prompts (⚡)
**Purpose:** Improve performance

**Characteristics:**
- Focus on speed/efficiency
- Provide benchmarks
- Suggest caching strategies
- Include profiling tips

**When to use:**
- Feature works but is slow
- Need better performance
- Want to reduce latency
- Optimizing for scale

---

### Testing Prompts (🧪)
**Purpose:** Verify functionality

**Characteristics:**
- Provide test scenarios
- Include edge cases
- Suggest test frameworks
- Define success criteria

**When to use:**
- After implementing fix
- Before deploying feature
- Adding new functionality
- Ensuring reliability

---

## 🎓 How to Write New Prompts

When you encounter a new issue pattern:

### 1. Document the Issue
```markdown
## 🔍 Diagnostic Prompt: [Clear Issue Title]

### Context
[Brief description of the issue]

### Prompt
```
[Your issue] is not working as expected.

Feature details:
- Component: [path]
- Expected behavior: [description]
- Observed behavior: [description]

Please investigate:
1. [First area to check]
2. [Second area to check]
...

Please provide:
- Root cause
- Specific code location
- Recommended fix
```
```

### 2. Create the Fix Template
```markdown
## 🔧 Fix Prompt: [Solution Title]

**Use when:** [Specific scenario]

```
[Action to take] for [feature name].

Requirements:
1. [First requirement with code example]
2. [Second requirement with code example]
...

Files to modify:
- [file path] ([what to change])
```
```

### 3. Add to Quick Reference
```markdown
| Issue | Diagnostic Prompt | Fix Prompt |
|-------|-------------------|-----------|
| [Issue] | [Diagnostic title] | [Fix title] |
```

### 4. Include Testing
```markdown
### Testing Checklist
- [ ] [Test case 1]
- [ ] [Test case 2]
...
```

---

## 📈 Metrics & Success Criteria

### For Diagnostic Prompts

**Good diagnostic prompt:**
- ✅ Identifies root cause in < 5 minutes
- ✅ Checks all relevant areas
- ✅ Provides actionable insights
- ✅ Includes specific code locations

**Needs improvement:**
- ❌ Too vague or generic
- ❌ Misses obvious causes
- ❌ Doesn't provide next steps
- ❌ Requires multiple iterations

### For Fix Prompts

**Good fix prompt:**
- ✅ Solves the issue completely
- ✅ Includes working code examples
- ✅ Follows best practices
- ✅ Adds proper error handling

**Needs improvement:**
- ❌ Partial solution
- ❌ Code doesn't compile/run
- ❌ Introduces new issues
- ❌ Lacks error handling

---

## 🔗 Related Documentation

### User-Facing Docs
- `QUICK_START.md` - Getting started with DynoAI
- `VIRTUAL_TUNING_QUICK_REFERENCE.md` - Virtual tuning guide
- `TROUBLESHOOTING_VIRTUAL_TUNING.md` - User troubleshooting

### Developer Docs
- `VIRTUAL_TUNING_COMPLETE_GUIDE.md` - Complete virtual tuning system
- `VIRTUAL_ECU_IMPLEMENTATION_SUMMARY.md` - Virtual ECU details
- `JETDRIVE_TESTING_OPTIONS.md` - JetDrive testing guide

### Architecture Docs
- `COMPLETE_VIRTUAL_TUNING_SYSTEM.md` - System architecture
- `SESSION_REPLAY_IMPLEMENTATION.md` - Replay system details
- `CONFIDENCE_SCORING_COMPLETE.md` - Confidence scoring system

---

## 🤝 Contributing

### Adding New Prompts

1. Identify a recurring issue pattern
2. Write diagnostic prompt using template
3. Create fix prompt with code examples
4. Add to appropriate document
5. Update this index
6. Test the prompt with AI assistant
7. Refine based on results

### Improving Existing Prompts

1. Note where prompt fell short
2. Add missing investigation areas
3. Improve code examples
4. Add edge cases
5. Update testing checklist
6. Document improvements

### Prompt Quality Guidelines

**Diagnostic Prompts Should:**
- Be comprehensive but focused
- Ask specific questions
- Provide investigation structure
- Request actionable output

**Fix Prompts Should:**
- Include working code
- Follow project conventions
- Add proper error handling
- Include testing steps

**All Prompts Should:**
- Be clear and concise
- Use consistent formatting
- Include examples
- Be maintainable

---

## 📞 Prompt Usage Examples

### Example 1: Using a Diagnostic Prompt

**Scenario:** Closed-loop tuning stuck at iteration 0

**Steps:**
1. Open `AGENT_PROMPTS_CLOSED_LOOP_DEBUGGING.md`
2. Find "Diagnostic Prompt: Closed-Loop Auto-Tune Stuck at Iteration 0"
3. Copy the entire prompt
4. Provide to AI assistant with context:

```
I'm using DynoAI and the closed-loop auto-tune feature is stuck at iteration 0/10 
with 5% progress for over 60 seconds. The backend logs show the session was created 
but no iteration logs appear.

[PASTE DIAGNOSTIC PROMPT HERE]
```

5. Review the analysis
6. Follow recommended investigation steps

### Example 2: Using a Fix Prompt

**Scenario:** Need to add exception handling to background thread

**Steps:**
1. Root cause identified: Thread failing silently
2. Open `AGENT_PROMPTS_CLOSED_LOOP_DEBUGGING.md`
3. Find "Fix Prompt 1: Add Exception Handling to Background Thread"
4. Copy the prompt
5. Provide to AI assistant:

```
The closed-loop tuning background thread is failing silently due to an exception 
in the dyno simulator. I need to add proper exception handling.

[PASTE FIX PROMPT HERE]

Additional context:
- File: api/routes/virtual_tune.py
- Lines: 92-98
- Exception: AttributeError in simulator.run_pull()
```

6. Review the generated code
7. Implement the fix
8. Test using the checklist

### Example 3: Combining Multiple Prompts

**Scenario:** Complex issue requiring multiple fixes

**Steps:**
1. Start with diagnostic prompt to identify all issues
2. Apply Fix Prompt 1 for exception handling
3. Apply Fix Prompt 2 for logging
4. Apply Fix Prompt 3 for timeout protection
5. Use testing checklist to verify all fixes
6. Document the solution

---

## 🎯 Success Stories

### Case Study 1: Closed-Loop Tuning Stuck at Iteration 0

**Issue:** Feature completely non-functional, stuck at 5% progress

**Prompts Used:**
1. Main diagnostic prompt
2. Fix Prompt 1 (exception handling)
3. Fix Prompt 2 (logging)

**Result:**
- Root cause identified in 3 minutes
- Fix implemented in 15 minutes
- Feature now works reliably
- Added logging prevents future issues

**Time Saved:** ~2 hours of manual debugging

### Case Study 2: Live Data Not Updating

**Issue:** JetDrive gauges showing stale data

**Prompts Used:**
1. "Live Data Not Updating" diagnostic
2. "Channel Name Mapping Debug" fix
3. Pattern 6 (Real-Time Streaming)

**Result:**
- Found channel name mismatch
- Added flexible mapping
- Optimized poll interval
- Gauges now update at 20 Hz

**Time Saved:** ~1 hour of debugging

### Case Study 3: Memory Leak in Session Storage

**Issue:** Backend memory growing indefinitely

**Prompts Used:**
1. Pattern 5 (Memory Leaks) diagnostic
2. Pattern 5 fix template

**Result:**
- Identified lack of cleanup
- Added automatic expiration
- Implemented cleanup endpoint
- Memory usage now stable

**Time Saved:** ~3 hours of profiling and debugging

---

## 📚 Appendix

### A. Prompt Template Library

#### Diagnostic Prompt Template
```markdown
## 🔍 Diagnostic Prompt: [Issue Title]

### Context
[Brief description]

### Prompt
```
[Issue description]

Feature details:
- Component: [path]
- Expected: [behavior]
- Observed: [behavior]

Please investigate:
1. [Area 1]
   - [Sub-item]
   - [Sub-item]
2. [Area 2]
3. [Area 3]

Please provide:
- Root cause
- Code location
- Recommended fix
- [Other specific requests]
```
```

#### Fix Prompt Template
```markdown
## 🔧 Fix Prompt: [Solution Title]

**Use when:** [Scenario]

```
[Action] for [feature].

Requirements:
1. [Requirement with code]
2. [Requirement with code]

Files to modify:
- [path] ([changes])

Example:
```[language]
[code example]
```
```
```

### B. Common Code Patterns

#### Thread-Safe State Update
```python
import threading

class StateManager:
    def __init__(self):
        self._state = {}
        self._lock = threading.Lock()
    
    def update(self, key, value):
        with self._lock:
            self._state[key] = value
```

#### React Query Polling
```typescript
const { data } = useQuery({
  queryKey: ['status', id],
  queryFn: fetchStatus,
  enabled: !!id,
  refetchInterval: (data) => 
    data?.status === 'running' ? 1000 : false
});
```

#### Progress Tracking
```python
def long_task(task_id):
    progress.update(task_id, 0, "Starting...")
    # Step 1
    progress.update(task_id, 25, "Step 1...")
    # Step 2
    progress.update(task_id, 50, "Step 2...")
    # Complete
    progress.update(task_id, 100, "Done!")
```

### C. Debugging Command Reference

```bash
# Check backend logs
tail -f logs/dynoai.log

# Test API endpoint
curl http://127.0.0.1:5001/api/virtual-tune/health

# Check React Query state
# Open React DevTools → Query tab

# Monitor network requests
# Open Browser DevTools → Network tab

# Check thread state
# Add endpoint: GET /api/debug/threads
```

---

## 🎉 Conclusion

This prompt library is a living document. As you encounter new patterns and solutions, add them here to help future debugging efforts.

**Remember:**
- Start with diagnostic prompts
- Apply fix prompts systematically
- Test thoroughly
- Document your findings
- Share improvements

**Happy debugging! 🚀**

---

**Last Updated:** December 15, 2025  
**Version:** 1.0  
**Maintainer:** DynoAI Development Team

