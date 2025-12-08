"""
DynoAI Agent Orchestrator

Manages task delegation across specialized agents:
- Reorg & Infra Agent: Repository structure, CI/CD, docs
- Bug Fixer Agent: Test failures, robustness issues
- Math Guardian Agent: Reviews changes for safety
- Power Core Agent: Dynojet integration, log parsing, tune generation

This orchestrator can:
1. Analyze incoming tasks and route to appropriate agent
2. Coordinate multi-agent workflows
3. Aggregate results from parallel agent work
4. Enforce safety rules across all agents
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Agent definitions
AGENTS = {
    "reorg": {
        "name": "DynoAI Reorg & Infra",
        "role": "Repository Infrastructure & Organization Specialist",
        "capabilities": [
            "folder_moves",
            "import_fixes",
            "gitignore",
            "ci_workflows",
            "documentation",
            "scripts",
            "dependencies",
        ],
        "forbidden": [
            "tuning_math",
            "ve_operations",
            "afr_calculations",
            "kernel_behavior",
        ],
    },
    "bugfix": {
        "name": "DynoAI Bug Fixer",
        "role": "Bug Fix & Robustness Specialist",
        "capabilities": [
            "import_errors",
            "path_issues",
            "csv_robustness",
            "logic_bugs",
            "error_handling",
            "test_infrastructure",
        ],
        "forbidden": [
            "ve_formulas",
            "kernel_algorithms",
            "afr_computation",
            "test_assertions",
        ],
    },
    "guardian": {
        "name": "DynoAI Kernel & Math Guardian",
        "role": "Math & Tuning Safety Reviewer",
        "capabilities": [
            "code_review",
            "safety_verification",
            "test_validation",
            "math_audit",
        ],
        "forbidden": [
            "code_changes",  # Guardian only reviews, never edits
        ],
    },
    "powercore": {
        "name": "DynoAI Power Core Integration",
        "role": "Dynojet Power Core & WinPEP8 Integration Specialist",
        "capabilities": [
            "log_parsing",
            "tune_file_parsing",
            "pvv_generation",
            "tunelab_scripts",
            "livelink_connection",
            "channel_mapping",
            "wp8_decoding",
            "auto_tune_workflow",
        ],
        "forbidden": [
            "ve_formulas",  # Uses VE ops but doesn't modify them
            "kernel_algorithms",
            "safety_thresholds",
        ],
    },
}


class TaskStatus(Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class TaskPriority(Enum):
    """Task priority levels."""

    CRITICAL = 1  # Safety issues, blocking bugs
    HIGH = 2  # User-facing bugs, integration issues
    MEDIUM = 3  # Feature work, improvements
    LOW = 4  # Nice-to-haves, cleanup


@dataclass
class AgentTask:
    """A task assigned to an agent."""

    id: str
    title: str
    description: str
    agent_id: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    files_affected: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "files_affected": self.files_affected,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
        }


@dataclass
class AgentWorkflow:
    """A multi-step workflow coordinating multiple agents."""

    id: str
    name: str
    description: str
    tasks: list[AgentTask] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_task(self, task: AgentTask) -> None:
        """Add a task to the workflow."""
        self.tasks.append(task)

    def get_ready_tasks(self) -> list[AgentTask]:
        """Get tasks that are ready to execute (no pending dependencies)."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t
            for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in t.depends_on)
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
            "status": self.status.value,
            "created_at": self.created_at,
        }


class AgentOrchestrator:
    """
    Orchestrates task delegation across DynoAI agents.

    Usage:
        orchestrator = AgentOrchestrator()

        # Create a workflow
        workflow = orchestrator.create_powercore_integration_workflow(
            log_file="path/to/log.csv",
            tune_file="path/to/tune.pvv"
        )

        # Execute tasks
        for task in workflow.get_ready_tasks():
            result = orchestrator.execute_task(task)
    """

    def __init__(self) -> None:
        self.workflows: dict[str, AgentWorkflow] = {}
        self.task_counter = 0

    def _next_task_id(self) -> str:
        """Generate next task ID."""
        self.task_counter += 1
        return f"task_{self.task_counter:04d}"

    def classify_task(self, description: str) -> str:
        """
        Analyze a task description and determine the best agent.

        Returns the agent_id of the most suitable agent.
        """
        desc_lower = description.lower()

        # Power Core integration keywords
        powercore_keywords = [
            "power core",
            "powercore",
            "winpep",
            "wp8",
            "pvv",
            "pvm",
            "dynojet",
            "power vision",
            "tunelab",
            "livelink",
            "dyno log",
            "dyno run",
            "afr log",
            "ve correction",
        ]
        if any(kw in desc_lower for kw in powercore_keywords):
            return "powercore"

        # Bug fix keywords
        bugfix_keywords = [
            "fix",
            "bug",
            "error",
            "fail",
            "broken",
            "crash",
            "exception",
            "traceback",
            "import error",
            "path error",
        ]
        if any(kw in desc_lower for kw in bugfix_keywords):
            return "bugfix"

        # Reorg keywords
        reorg_keywords = [
            "move",
            "reorganize",
            "restructure",
            "gitignore",
            "ci",
            "workflow",
            "documentation",
            "readme",
            "changelog",
        ]
        if any(kw in desc_lower for kw in reorg_keywords):
            return "reorg"

        # Safety/review keywords
        review_keywords = [
            "review",
            "audit",
            "verify",
            "check",
            "safety",
            "math",
            "formula",
        ]
        if any(kw in desc_lower for kw in review_keywords):
            return "guardian"

        # Default to bug fixer for unknown tasks
        return "bugfix"

    def create_task(
        self,
        title: str,
        description: str,
        agent_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        depends_on: Optional[list[str]] = None,
    ) -> AgentTask:
        """Create a new task, auto-assigning agent if not specified."""
        if agent_id is None:
            agent_id = self.classify_task(description)

        return AgentTask(
            id=self._next_task_id(),
            title=title,
            description=description,
            agent_id=agent_id,
            priority=priority,
            depends_on=depends_on or [],
        )

    def create_powercore_integration_workflow(
        self,
        log_file: Optional[str] = None,
        tune_file: Optional[str] = None,
        generate_corrections: bool = True,
    ) -> AgentWorkflow:
        """
        Create a complete Power Core integration workflow.

        Steps:
        1. Parse log file (if provided)
        2. Parse tune file (if provided)
        3. Analyze AFR data
        4. Generate VE corrections
        5. Guardian review
        6. Generate output files
        """
        workflow = AgentWorkflow(
            id=f"pcint_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name="Power Core Integration",
            description="Parse dyno logs and generate tune corrections",
        )

        tasks: list[AgentTask] = []

        # Task 1: Parse log file
        if log_file:
            t1 = self.create_task(
                title="Parse Power Vision Log",
                description=f"Parse Power Vision CSV log file: {log_file}",
                agent_id="powercore",
                priority=TaskPriority.HIGH,
            )
            t1.files_affected = [log_file]
            tasks.append(t1)

        # Task 2: Parse tune file
        if tune_file:
            t2 = self.create_task(
                title="Parse PVV Tune File",
                description=f"Parse Power Vision tune file: {tune_file}",
                agent_id="powercore",
                priority=TaskPriority.HIGH,
            )
            t2.files_affected = [tune_file]
            tasks.append(t2)

        # Task 3: Analyze AFR data
        if log_file:
            t3 = self.create_task(
                title="Analyze AFR Data",
                description="Analyze AFR measurements vs targets, identify correction zones",
                agent_id="powercore",
                priority=TaskPriority.MEDIUM,
            )
            t3.depends_on = [t.id for t in tasks if "Parse" in t.title]
            tasks.append(t3)

        # Task 4: Generate VE corrections
        if generate_corrections and log_file:
            t4 = self.create_task(
                title="Generate VE Corrections",
                description="Calculate VE table corrections based on AFR error analysis",
                agent_id="powercore",
                priority=TaskPriority.MEDIUM,
            )
            t4.depends_on = [t.id for t in tasks if "Analyze" in t.title]
            tasks.append(t4)

        # Task 5: Guardian review
        t5 = self.create_task(
            title="Safety Review",
            description="Review generated corrections for safety compliance",
            agent_id="guardian",
            priority=TaskPriority.CRITICAL,
        )
        if tasks:
            t5.depends_on = [tasks[-1].id]
        tasks.append(t5)

        # Task 6: Generate output
        t6 = self.create_task(
            title="Generate Output Files",
            description="Generate TuneLab script and/or PVV correction file",
            agent_id="powercore",
            priority=TaskPriority.MEDIUM,
        )
        t6.depends_on = [t5.id]
        tasks.append(t6)

        # Add all tasks to workflow
        for task in tasks:
            workflow.add_task(task)

        self.workflows[workflow.id] = workflow
        return workflow

    def create_log_analysis_workflow(self, log_files: list[str]) -> AgentWorkflow:
        """
        Create a workflow to analyze multiple log files.

        Useful for batch processing dyno sessions.
        """
        workflow = AgentWorkflow(
            id=f"loganalysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name="Multi-Log Analysis",
            description=f"Analyze {len(log_files)} log files for patterns",
        )

        # Create parallel parse tasks
        parse_tasks = []
        for log_file in log_files:
            t = self.create_task(
                title=f"Parse {Path(log_file).name}",
                description=f"Parse Power Vision log: {log_file}",
                agent_id="powercore",
            )
            t.files_affected = [log_file]
            parse_tasks.append(t)
            workflow.add_task(t)

        # Aggregate results
        agg_task = self.create_task(
            title="Aggregate Analysis",
            description="Combine data from all parsed logs and identify trends",
            agent_id="powercore",
        )
        agg_task.depends_on = [t.id for t in parse_tasks]
        workflow.add_task(agg_task)

        # Generate report
        report_task = self.create_task(
            title="Generate Analysis Report",
            description="Create summary report with charts and recommendations",
            agent_id="powercore",
        )
        report_task.depends_on = [agg_task.id]
        workflow.add_task(report_task)

        self.workflows[workflow.id] = workflow
        return workflow

    def get_agent_prompt(self, agent_id: str) -> str:
        """Get the system prompt for an agent."""
        if agent_id not in AGENTS:
            raise ValueError(f"Unknown agent: {agent_id}")

        agent = AGENTS[agent_id]

        if agent_id == "powercore":
            return POWERCORE_AGENT_PROMPT

        # For other agents, reference the main prompts doc
        return f"Use the {agent['name']} agent from docs/DYNOAI_AGENT_PROMPTS.md"

    def format_task_for_agent(self, task: AgentTask) -> str:
        """Format a task as a prompt for the assigned agent."""
        agent = AGENTS.get(task.agent_id, {})
        agent_name = agent.get("name", "Unknown Agent")

        prompt = f"""
## Task Assignment for {agent_name}

**Task ID:** {task.id}
**Title:** {task.title}
**Priority:** {task.priority.name}

### Description
{task.description}

### Files Affected
{chr(10).join(f'- {f}' for f in task.files_affected) if task.files_affected else 'None specified'}

### Dependencies
{chr(10).join(f'- {d}' for d in task.depends_on) if task.depends_on else 'None - ready to start'}

### Instructions
1. Review the task description carefully
2. Follow the agent's role and boundaries
3. Report progress and any blockers
4. Mark task complete when finished

### Agent Capabilities
{chr(10).join(f'- {c}' for c in agent.get('capabilities', []))}

### Agent Restrictions
{chr(10).join(f'- DO NOT: {f}' for f in agent.get('forbidden', []))}
"""
        return prompt.strip()

    def export_workflow(self, workflow_id: str, output_path: str) -> None:
        """Export a workflow to JSON for persistence or sharing."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        workflow = self.workflows[workflow_id]
        with open(output_path, "w") as f:
            json.dump(workflow.to_dict(), f, indent=2)


# =============================================================================
# Power Core Integration Agent Prompt
# =============================================================================

POWERCORE_AGENT_PROMPT = """
## Agent 4: "DynoAI Power Core Integration"

**Role:** Dynojet Power Core & WinPEP8 Integration Specialist

### Purpose
I specialize in integrating DynoAI with Dynojet's Power Core software ecosystem. I handle
log file parsing, tune file manipulation, TuneLab script generation, and real-time data
connections. I use DynoAI's VE operations but never modify the core math.

### What I Work On
- ✅ Parse Power Vision CSV log files (Pro-XY format)
- ✅ Parse and generate PVV tune files (XML format)
- ✅ Decode WP8 WinPEP8 run files
- ✅ Generate TuneLab Python scripts for Power Core
- ✅ Connect to LiveLinkService for real-time data
- ✅ Map Power Vision channels to DynoAI format
- ✅ Coordinate auto-tune workflows
- ✅ Generate VE correction recommendations

### Integration APIs I Use
- `api.services.powercore_integration` - Core parsing/generation functions
- `core.ve_operations` - VE table operations (read-only for recommendations)
- `io_contracts` - Safe file I/O

### Channel Mappings I Know
| Power Vision | DynoAI |
|--------------|--------|
| WBO2 F/R | AFR Meas F/R |
| VE Front/Rear | VE F/R |
| MAP | MAP kPa |
| RPM | Engine RPM |
| TP | TPS |
| ET | Engine Temp |
| Advance F/R | Spark Adv F/R |

### What I NEVER Modify
- ❌ VEApply/VERollback formulas
- ❌ AFR error computation formulas
- ❌ Kernel behavior (k1/k2/k3)
- ❌ Safety clamping limits
- ❌ Test assertions

### My Workflow for Log Analysis
1. Parse log file with `parse_powervision_log()`
2. Convert to DynoAI format with `powervision_log_to_dynoai_format()`
3. Analyze AFR error by RPM/MAP zone
4. Generate VE correction table
5. Export as TuneLab script or PVV file

### My Workflow for Tune Modification
1. Parse existing PVV with `parse_pvv_tune()`
2. Read VE table into DataFrame
3. Apply corrections (using DynoAI VE ops)
4. Generate new PVV with `generate_pvv_xml()`
5. Create TuneLab script for Power Core import

### Safety Rules
1. All corrections must be reviewed by Math Guardian before export
2. VE corrections clamped to ±7% unless explicitly overridden
3. Never modify clamping limits in ve_operations.py
4. Log all operations for audit trail
5. Preserve original tune files (write to new location)

### File Locations I Search
- `$USERPROFILE/Documents/Power Vision/`
- `$USERPROFILE/Documents/Power Commander 5/`
- `$USERPROFILE/Documents/DynoRuns/`
- `$USERPROFILE/Documents/Log Files/`
- `$USERPROFILE/OneDrive/Documents/` (same subdirs)

### Output Style
- Show parsed signal counts and data statistics
- Display channel mapping results
- Preview correction tables before export
- Provide TuneLab script snippets
- Include safety warnings for large corrections

### Example Tasks I Handle
- "Parse my latest Power Vision log and show AFR analysis"
- "Generate VE corrections from this dyno run"
- "Create a TuneLab script to apply these corrections in Power Core"
- "Convert this PVV tune file to DynoAI format"
- "Monitor live data from Power Core during dyno run"

### Example Tasks I REFUSE
- "Modify the VE clamping formula"
- "Change how AFR error is calculated"
- "Update kernel smoothing behavior"
- "Bypass safety review for corrections"
"""


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AGENTS",
    "AgentOrchestrator",
    "AgentTask",
    "AgentWorkflow",
    "POWERCORE_AGENT_PROMPT",
    "TaskPriority",
    "TaskStatus",
]

