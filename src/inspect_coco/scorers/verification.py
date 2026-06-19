"""Verification scorer — runs test command in sandbox and reports pass/fail."""

from __future__ import annotations

from inspect_ai.scorer import (
    Metric,
    Score,
    Target,
    Value,
    metric,
    scorer,
)
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox


@metric
def passed() -> Metric:
    """Count of passing samples."""

    def metric_fn(scores: list[Score]) -> Value:
        return sum(1 for s in scores if s.value == 1.0)

    return metric_fn


@metric
def total() -> Metric:
    """Total number of samples scored."""

    def metric_fn(scores: list[Score]) -> Value:
        return len(scores)

    return metric_fn


@scorer(metrics=[passed(), total()])
def verification(test_cmd: str = "bash /workspace/tests/test.sh", timeout: int = 300):
    """Score by running a test command in the sandbox.

    Executes the test command inside the Docker sandbox after the agent
    completes. Exit code 0 = pass (1.0), non-zero = fail (0.0).

    Args:
        test_cmd: Shell command to run in the sandbox.
        timeout: Maximum seconds for test execution.
    """

    async def score(state: TaskState, target: Target) -> Score:
        result = await sandbox().exec(
            cmd=["bash", "-c", test_cmd],
            timeout=timeout,
        )

        is_pass = result.returncode == 0

        return Score(
            value=1.0 if is_pass else 0.0,
            answer=state.output.completion if state.output else "",
            explanation=result.stdout if is_pass else f"EXIT {result.returncode}\n{result.stderr}",
        )

    return score
