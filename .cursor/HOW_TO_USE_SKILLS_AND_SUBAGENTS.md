# How to Use DynoAI Skills and Subagents

## Skills (Passive Knowledge)

Skills are **automatically considered** by the agent when your request matches their description. You don't have to "call" them — just describe what you want.

### When each skill activates

| Skill | Trigger phrases / scenarios |
|-------|-----------------------------|
| **dynoai-domain-expert** | "VE table", "AFR", "JetDrive", "cylinder balance", "zone classification", "VE correction", editing any DynoAI source file |
| **dynoai-fullstack-feature** | "Add a new feature", "scaffold a wizard", "create a new API with frontend", "new page with backend" |
| **dynoai-test-generator** | "Add tests", "write tests for...", "set up Vitest", "test coverage", "generate tests" |
| **dynoai-api-contract-sync** | "Type mismatch", "sync types", "API contract", "update frontend types from backend", "type drift" |
| **dynoai-component-splitter** | "Split this component", "refactor TuningWizard", "break up large component", "decompose..." |

### How to use skills

1. **Be specific** — e.g. "Add a Heat Soak Wizard following our full-stack pattern" so the fullstack-feature skill is used.
2. **Mention the domain** — e.g. "Fix the zone classification for decel" so the domain-expert skill is included.
3. **Ask for the workflow** — e.g. "Add tests for the VE apply utils" so the test-generator skill is applied.

You can also **@ mention** a skill file if you want to force it: e.g. `@.cursor/skills/dynoai-domain-expert/SKILL.md` in the chat.

---

## Subagents (Active Workers)

Subagents are **separate agents** the main Cursor agent can spawn. Each runs in its own context and returns a result. The main agent decides when to use them based on your task.

### When each subagent is used

| Subagent | Typical use |
|----------|-------------|
| **VE Math Verifier** | After editing VE math, or when you ask to "verify tuning safety" or "check VE corrections" |
| **Frontend UI Agent** | Frontend-only work: "build this component", "fix the JetDrive page layout", "add a hook for..." |
| **Backend API Agent** | Backend-only work: "add an endpoint for...", "create a new Flask route", "fix the virtual tune service" |
| **JetDrive Hardware Agent** | "Fix multicast discovery", "debug JetDrive connection", "serial port", "live data not updating" |
| **PR Reviewer** | "Review this PR", "check my changes", "verify this implementation" |
| **Test Agent** | "Add tests for this", "run tests", "set up frontend testing", "verify with tests" |
| **DevOps Agent** | "Docker won't start", "fix npm install", "CI is failing", "update startup script" |

### How to use subagents

1. **Ask for the outcome** — e.g. "Review my last commit" → main agent may spawn PR Reviewer.
2. **Ask for parallel work** — e.g. "Add the Heat Soak feature: backend API and frontend page" → main agent may spawn Backend + Frontend agents in parallel.
3. **Ask explicitly** — e.g. "Run the VE Math Verifier on the apply workflow" or "Have the test agent add tests for veApply utils."

You can also **invoke a subagent by name** in Cursor (if your version supports it) via the agent/subagent list in the UI.

### Where they live

- **Skills:** `.cursor/skills/<name>/SKILL.md` (and optional reference files).
- **Subagents:** `.cursor/agents/<name>.md`.

Both are project-level, so they apply to this repo for anyone using it.

---

## Quick Examples

| You say | What happens |
|---------|----------------|
| "Add a new Decel Pop wizard with API and a page" | Main agent uses **dynoai-fullstack-feature** skill, may spawn **Backend API** and **Frontend UI** subagents. |
| "Verify the VE apply math is safe" | Main agent spawns **VE Math Verifier** (readonly); you get a pass/warn/block report. |
| "Review the changes in my branch" | Main agent spawns **PR Reviewer**; you get structured feedback (critical / suggestion / good). |
| "Add tests for the zone classification and cylinder balance utils" | Main agent uses **dynoai-test-generator** skill and may spawn **Test Agent** to create and run tests. |
| "Docker build is failing on Windows" | Main agent spawns **DevOps Agent** to inspect Dockerfiles, compose files, and scripts. |
| "Why isn’t JetDrive live data updating?" | Main agent spawns **JetDrive Hardware Agent** to check multicast, polling, and API. |

---

## Summary

- **Skills** = knowledge and patterns the agent uses when your question matches (passive).
- **Subagents** = dedicated agents the main agent can spin up for focused or parallel work (active).

Describe what you want in normal language; the agent picks the right skills and subagents. For more control, mention the domain (e.g. "VE math") or the kind of task (e.g. "review", "tests", "DevOps") or name the subagent you want.
