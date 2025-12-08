"""Test the agent orchestrator."""

import sys
from pathlib import Path

from api.services.agent_orchestrator import AGENTS, AgentOrchestrator

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_agent_orchestrator():
    """Test the agent orchestrator."""
    print("=== Agent Orchestrator Test ===")
    print()
    print("Available Agents:")
    for agent_id, agent in AGENTS.items():
        print(f"  {agent_id}: {agent['name']}")
        print(f"    Role: {agent['role']}")
    print()

    # Test task classification
    orchestrator = AgentOrchestrator()

    test_tasks = [
        "Parse my Power Vision log and analyze AFR",
        "Fix the import error in test_k2.py",
        "Move tests to the tests directory",
        "Review the changes to ve_operations.py",
        "Generate TuneLab script for VE correction",
    ]

    print("Task Classification:")
    for task in test_tasks:
        agent = orchestrator.classify_task(task)
        print(f'  "{task[:50]}..."')
        print(f"    -> {AGENTS[agent]['name']}")
    print()

    # Test workflow creation
    workflow = orchestrator.create_powercore_integration_workflow(
        log_file="test_log.csv",
        tune_file="test_tune.pvv",
        generate_corrections=True,
    )

    print(f"Created Workflow: {workflow.name}")
    print(f"Tasks: {len(workflow.tasks)}")
    for task in workflow.tasks:
        agent = AGENTS[task.agent_id]["name"]
        deps = f" (depends on: {task.depends_on})" if task.depends_on else ""
        print(f"  [{task.id}] {task.title} -> {agent}{deps}")

    print()
    print("=== Test Complete ===")


if __name__ == "__main__":
    test_agent_orchestrator()
