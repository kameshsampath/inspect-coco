"""Task loader — reads task.toml + instruction.md and produces Inspect Tasks."""

from __future__ import annotations

import logging
from pathlib import Path

import toml
from inspect_ai import Task, task
from inspect_ai.agent import as_solver
from inspect_ai.dataset import MemoryDataset, Sample

from inspect_coco.agents import coco
from inspect_coco.idd import explain_score, score_instruction
from inspect_coco.scorers import idd_quality, verification

logger = logging.getLogger(__name__)

# Path to built-in sandbox compose
BUILTIN_COMPOSE = Path(__file__).parent.parent / "sandbox" / "compose.yaml"

# Default epochs for consistency measurement (pass@k)
DEFAULT_EPOCHS = 3

# Default IDD threshold
DEFAULT_IDD_THRESHOLD = 0.6


@task
def coco_task(
    task_dir: str,
    timeout_sec: int = 900,
    epochs: int | None = None,
    idd_threshold: float | None = None,
    idd_strict: bool = False,
) -> Task:
    """Load a CoCo eval task from a task.toml directory.

    Reads task configuration, instruction, and test script. Runs IDD
    pre-check on the instruction and configures the Inspect Task with
    auto-epochs for consistency measurement.

    Args:
        task_dir: Path to directory containing task.toml + instruction.md.
        timeout_sec: Default agent timeout (overridden by task.toml).
        epochs: Number of epochs for pass@k (default: 3, overridden by task.toml).
        idd_threshold: IDD score threshold (default: 0.6, overridden by task.toml).
        idd_strict: If True, fail below threshold instead of warning.
    """
    task_path = Path(task_dir)

    # Load task.toml
    config = _load_task_config(task_path)
    metadata = config.get("metadata", {})
    agent_config = config.get("agent", {})
    env_config = config.get("environment", {})

    # Load instruction.md
    instruction = _load_instruction(task_path)

    # IDD pre-check
    threshold = idd_threshold or metadata.get("idd_threshold", DEFAULT_IDD_THRESHOLD)
    strict = idd_strict or metadata.get("idd_strict", False)
    idd_metadata = _run_idd_check(instruction, threshold, strict, task_path.name)

    # Merge IDD scores into task metadata (persisted in eval log)
    metadata = {**metadata, **idd_metadata}

    # Resolve epochs (auto-epochs for consistency measurement)
    resolved_epochs = epochs or metadata.get("epochs", DEFAULT_EPOCHS)

    # Resolve sandbox
    sandbox_spec = _resolve_sandbox(task_path, env_config)

    # Build dataset
    dataset = _build_dataset(instruction, task_path)

    # Build agent solver
    agent_solver = as_solver(
        coco(
            timeout_sec=agent_config.get("timeout_sec", timeout_sec),
            max_turns=agent_config.get("max_turns"),
            remove_skills=agent_config.get("remove_skills"),
            model_name=agent_config.get("model"),
            connection_name=agent_config.get("connection"),
            workdir=agent_config.get("workdir", "/workspace"),
        )
    )

    # Build scorers
    test_cmd = _resolve_test_cmd(task_path, env_config)
    scorers = [
        verification(test_cmd=test_cmd, timeout=env_config.get("test_timeout", 300)),
        idd_quality(instruction=instruction, threshold=threshold),
    ]

    return Task(
        dataset=dataset,
        solver=agent_solver,
        scorer=scorers,
        sandbox=sandbox_spec,
        epochs=resolved_epochs,
        name=metadata.get("name", task_path.name),
        metadata=metadata,
    )


def _load_task_config(task_path: Path) -> dict:
    """Load and parse task.toml."""
    toml_path = task_path / "task.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"task.toml not found in {task_path}")
    return toml.load(toml_path)


def _load_instruction(task_path: Path) -> str:
    """Load instruction.md content."""
    instruction_path = task_path / "instruction.md"
    if not instruction_path.exists():
        raise FileNotFoundError(f"instruction.md not found in {task_path}")
    return instruction_path.read_text()


def _run_idd_check(instruction: str, threshold: float, strict: bool, task_name: str) -> dict:
    """Run IDD pre-check on instruction. Returns IDD metadata for the eval log."""
    idd_score = score_instruction(instruction)
    explanation = explain_score(idd_score, threshold=threshold)

    if idd_score.total < threshold:
        if strict:
            raise IDDThresholdError(
                f"Task '{task_name}' instruction below IDD threshold "
                f"({idd_score.total:.2f} < {threshold}).\n\n{explanation}"
            )
        else:
            logger.warning(
                "Task '%s' instruction IDD score: %.2f (threshold: %.2f)\n%s",
                task_name,
                idd_score.total,
                threshold,
                explanation,
            )
    else:
        logger.info(
            "Task '%s' IDD pre-check passed (%.2f >= %.2f)",
            task_name,
            idd_score.total,
            threshold,
        )

    # Return IDD metadata to persist in eval log
    return {
        "idd_score": idd_score.total,
        "idd_goal": idd_score.goal.score,
        "idd_requirements": idd_score.requirements.score,
        "idd_constraints": idd_score.constraints.score,
        "idd_output": idd_score.output.score,
        "idd_ambiguity_count": idd_score.ambiguity_count,
        "idd_specificity": idd_score.specificity,
        "idd_threshold": threshold,
        "idd_passed": idd_score.total >= threshold,
    }


def _resolve_sandbox(task_path: Path, env_config: dict) -> tuple[str, str]:
    """Resolve sandbox spec: task-dir compose > task.toml path > builtin."""
    # 1. Check for compose.yaml in task directory (Inspect auto-discovery)
    task_compose = task_path / "compose.yaml"
    if task_compose.exists():
        return ("docker", str(task_compose))

    # 2. Check for explicit path in task.toml [environment]
    if "compose" in env_config:
        compose_path = task_path / env_config["compose"]
        if compose_path.exists():
            return ("docker", str(compose_path))

    # 3. Fall back to built-in
    return ("docker", str(BUILTIN_COMPOSE))


def _build_dataset(instruction: str, task_path: Path) -> MemoryDataset:
    """Build dataset from instruction and optional starter files."""
    sample_kwargs: dict = {"input": instruction}

    files: dict[str, str] = {}

    # Copy starter/ files into /workspace/
    starter_dir = task_path / "starter"
    if starter_dir.exists() and starter_dir.is_dir():
        for f in starter_dir.rglob("*"):
            if f.is_file():
                rel_path = f.relative_to(starter_dir)
                files[f"/workspace/{rel_path}"] = str(f)

    # Copy tests/ files into /workspace/tests/ (needed by scorer)
    tests_dir = task_path / "tests"
    if tests_dir.exists() and tests_dir.is_dir():
        for f in tests_dir.rglob("*"):
            if f.is_file():
                rel_path = f.relative_to(tests_dir)
                files[f"/workspace/tests/{rel_path}"] = str(f)

    if files:
        sample_kwargs["files"] = files

    return MemoryDataset([Sample(**sample_kwargs)], name=task_path.name)


def _resolve_test_cmd(task_path: Path, env_config: dict) -> str:
    """Resolve the test command to run."""
    if "test_cmd" in env_config:
        return env_config["test_cmd"]

    # Default: look for tests/test.sh in task dir
    test_sh = task_path / "tests" / "test.sh"
    if test_sh.exists():
        return "bash /workspace/tests/test.sh"

    return "bash /workspace/tests/test.sh"


class IDDThresholdError(Exception):
    """Raised when instruction IDD score is below threshold in strict mode."""
