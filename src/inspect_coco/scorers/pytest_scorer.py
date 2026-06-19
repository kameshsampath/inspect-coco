"""Pytest scorer — runs test.sh in the sandbox and maps exit code to Score."""

from __future__ import annotations

from inspect_ai.scorer import (
    Score,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox


@scorer(metrics=[accuracy()])
def pytest_scorer(test_cmd: str = "bash /workspace/tests/test.sh", timeout: int = 300):
    """Score an eval by running a test script in the sandbox.

    Executes the test command inside the Docker sandbox after the agent
    has completed. Exit code 0 = pass (1.0), non-zero = fail (0.0).

    Args:
        test_cmd: Shell command to run in the sandbox. Default: bash /workspace/tests/test.sh
        timeout: Maximum seconds for test execution.
    """

    async def score(state: TaskState, target: Target) -> Score:
        result = await sandbox().exec(
            cmd=["bash", "-c", test_cmd],
            timeout=timeout,
        )

        passed = result.returncode == 0

        return Score(
            value=1.0 if passed else 0.0,
            answer=state.output.completion if state.output else "",
            explanation=result.stdout if passed else f"EXIT {result.returncode}\n{result.stderr}",
        )

    return score
