# DynoAI Agent Prompts

This directory contains individual agent prompt files that can be easily copied and pasted into various AI coding assistants.

## Available Agents

### 1. Reorg & Infra Agent
**File:** `agent1_reorg_infra.md`  
**Use for:** Repository organization, CI/CD, documentation, infrastructure changes  
**Never touches:** Tuning math, kernels, VE/AFR behavior

### 2. Bug Fixer Agent
**File:** `agent2_bug_fixer.md`  
**Use for:** Fixing failing tests, bugs, robustness issues  
**Never touches:** Tuning algorithms, kernel behavior, test assertions

### 3. Kernel & Math Guardian Agent
**File:** `agent3_math_guardian.md`  
**Use for:** Reviewing PRs and diffs for safety violations  
**Role:** Reviewer only - does not make edits

## How to Use

### In Cursor
1. Open Cursor Settings
2. Navigate to Composer Rules
3. Click "Add Rule"
4. Name it (e.g., "DynoAI Reorg Agent")
5. Copy the content from the relevant `.md` file
6. Paste into the rule content
7. Use `@rules` in Composer to activate

### In ChatGPT (Custom Instructions)
1. Open ChatGPT
2. Go to Settings → Custom Instructions
3. Copy the content from the relevant `.md` file
4. Paste in "How would you like ChatGPT to respond?"
5. Save and start chatting

### In GitHub Copilot Chat
1. Open GitHub Copilot Chat
2. Reference the file: 
   ```
   @workspace Act as the DynoAI Bug Fixer agent from docs/prompts/agent2_bug_fixer.md
   ```
3. Copilot will follow the agent's rules

### In Claude (Projects)
1. Create a new Project in Claude
2. Add the relevant `.md` file as project knowledge
3. In your conversation, reference:
   ```
   Follow the DynoAI Reorg Agent guidelines from the uploaded prompt file
   ```

## Quick Reference

| Task | Use Agent | File |
|------|-----------|------|
| Reorganize folders | Reorg & Infra | `agent1_reorg_infra.md` |
| Add .gitignore rules | Reorg & Infra | `agent1_reorg_infra.md` |
| Update CI workflows | Reorg & Infra | `agent1_reorg_infra.md` |
| Fix import errors | Bug Fixer | `agent2_bug_fixer.md` |
| Fix failing tests | Bug Fixer | `agent2_bug_fixer.md` |
| Handle CSV issues | Bug Fixer | `agent2_bug_fixer.md` |
| Review PR safety | Math Guardian | `agent3_math_guardian.md` |
| Check for math changes | Math Guardian | `agent3_math_guardian.md` |
| Verify test integrity | Math Guardian | `agent3_math_guardian.md` |

## Agent Collaboration Example

Agents can work together on complex tasks:

**Scenario:** Repository reorganization
1. **Reorg Agent**: Move files to new structure
2. **Bug Fixer**: Fix any broken imports
3. **Math Guardian**: Verify no math was affected

**Workflow:**
```bash
# Step 1: Reorg Agent moves files
# Step 2: Bug Fixer fixes imports and tests
# Step 3: Math Guardian reviews the changes

# Math Guardian output:
VERDICT: PASS
- Files changed: 15 (structural only)
- Math-critical files: 0 (imports updated only)
- All tests passing: ✅
Recommendation: Approve and merge
```

## Full Documentation

For the complete documentation including examples, output formats, and detailed guidelines, see:
- **Main Document:** [`../DYNOAI_AGENT_PROMPTS.md`](../DYNOAI_AGENT_PROMPTS.md)

## Related Documentation

- [DynoAI Safety Rules](../DYNOAI_SAFETY_RULES.md)
- [DynoAI Architecture Overview](../DYNOAI_ARCHITECTURE_OVERVIEW.md)

---

**Remember:** These agents exist to protect DynoAI's tuning accuracy and customer safety! 🏍️
