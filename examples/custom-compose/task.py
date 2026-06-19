"""Custom Compose eval task."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import as_solver
from inspect_ai.dataset import MemoryDataset, Sample

from inspect_coco.agents import coco
from inspect_coco.scorers import pytest_scorer

TASK_DIR = Path(__file__).parent


@task
def custom_compose() -> Task:
    """Demonstrates custom Docker Compose environment."""
    instruction = (TASK_DIR / "instruction.md").read_text()

    return Task(
        dataset=MemoryDataset([Sample(input=instruction)]),
        solver=as_solver(coco(timeout_sec=600, max_turns=15)),
        scorer=pytest_scorer(test_cmd="bash /workspace/tests/test.sh"),
        sandbox=("docker", str(TASK_DIR / "compose.yaml")),
        epochs=3,
    )
