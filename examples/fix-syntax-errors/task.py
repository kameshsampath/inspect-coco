"""Fix Syntax Errors eval task."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import as_solver
from inspect_ai.dataset import MemoryDataset, Sample

from inspect_coco.agents import coco
from inspect_coco.scorers import pytest_scorer

TASK_DIR = Path(__file__).parent


@task
def fix_syntax_errors() -> Task:
    """Code repair eval - fix broken Python."""
    instruction = (TASK_DIR / "instruction.md").read_text()

    # Starter files copied to /workspace
    files = {"/workspace/broken.py": str(TASK_DIR / "starter" / "broken.py")}

    return Task(
        dataset=MemoryDataset([Sample(input=instruction, files=files)]),
        solver=as_solver(coco(timeout_sec=600, max_turns=15)),
        scorer=pytest_scorer(test_cmd="bash /workspace/tests/test.sh"),
        sandbox=(
            "docker",
            str(Path(__file__).parents[2] / "src" / "inspect_coco" / "sandbox" / "compose.yaml"),
        ),
        epochs=3,
    )
