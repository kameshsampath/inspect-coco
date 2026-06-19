"""Verification scorer — runs test command in sandbox and reports pass/fail."""

from __future__ import annotations

from inspect_ai.scorer import (
    Metric,
    SampleScore,
    Score,
    Target,
    Value,
    metric,
    scorer,
)
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox


@metric(name="Pass Rate")
def pass_rate() -> Metric:
    """Proportion of passing samples (0.0 to 1.0)."""

    def metric_fn(scores: list[SampleScore]) -> Value:
        if not scores:
            return 0.0
        passed = sum(1 for s in scores if s.score.value == 1.0)
        return round(passed / len(scores), 2)

    return metric_fn


@scorer(metrics=[pass_rate()], name="Verification")
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
