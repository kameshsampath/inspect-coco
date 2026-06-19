"""IDD quality scorer — surfaces instruction quality score in eval results."""

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


@metric
def idd_score() -> Metric:
    """Average IDD quality score across samples."""

    def metric_fn(scores: list[Score]) -> Value:
        vals = [s.value for s in scores if isinstance(s.value, int | float)]
        return sum(vals) / len(vals) if vals else 0.0

    return metric_fn


@scorer(metrics=[idd_score()])
def idd_quality(instruction: str, threshold: float = 0.6):
    """Score the IDD quality of the instruction.

    This scorer runs once per sample and reports the IDD quality score.
    It does not depend on sandbox execution.

    Args:
        instruction: The raw instruction text to score.
        threshold: Pass threshold for IDD score.
    """
    from inspect_coco.idd import score_instruction

    idd = score_instruction(instruction)

    async def score(state: TaskState, target: Target) -> Score:
        return Score(
            value=idd.total,
            answer=f"goal={idd.goal.score:.2f} req={idd.requirements.score:.2f} "
            f"con={idd.constraints.score:.2f} out={idd.output.score:.2f}",
            explanation=f"IDD={idd.total:.2f} (threshold={threshold})",
            metadata={
                "idd_goal": idd.goal.score,
                "idd_requirements": idd.requirements.score,
                "idd_constraints": idd.constraints.score,
                "idd_output": idd.output.score,
                "idd_passed": idd.total >= threshold,
            },
        )

    return score
