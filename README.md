# DynoAI_3

Intelligent dyno tuning system for Harley-Davidson ECM calibration.

## Documentation

- **[Agent Prompts](docs/DYNOAI_AGENT_PROMPTS.md)** - Three specialized coding agent prompts for safe DynoAI development
- **[Architecture Overview](docs/DYNOAI_ARCHITECTURE_OVERVIEW.md)** - System architecture and component interactions
- **[Safety Rules](docs/DYNOAI_SAFETY_RULES.md)** - Critical safety policies and invariants

## Quick Start: Using DynoAI Agents

This repository includes three specialized agent prompts that can be used with Cursor, ChatGPT, or GitHub Copilot:

### 1. Reorg & Infra Agent
**Purpose:** Repository organization, CI/CD, documentation  
**File:** [`docs/prompts/agent1_reorg_infra.md`](docs/prompts/agent1_reorg_infra.md)  
**Never touches:** Tuning math, kernels, VE/AFR behavior

### 2. Bug Fixer Agent
**Purpose:** Fix failing tests, bugs, robustness issues  
**File:** [`docs/prompts/agent2_bug_fixer.md`](docs/prompts/agent2_bug_fixer.md)  
**Never touches:** Tuning algorithms, kernel behavior

### 3. Kernel & Math Guardian Agent
**Purpose:** Review PRs for safety violations  
**File:** [`docs/prompts/agent3_math_guardian.md`](docs/prompts/agent3_math_guardian.md)  
**Role:** Reviewer only - does not make edits

**See [Agent Prompts Documentation](docs/DYNOAI_AGENT_PROMPTS.md) for complete usage instructions.**