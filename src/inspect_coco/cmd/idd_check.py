"""inspect-coco idd-check — check IDD scores without running evals."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from inspect_coco.idd import explain_score, score_instruction


@click.command("idd-check")
@click.argument("path", type=click.Path(exists=True))
@click.option("--threshold", type=float, default=0.6, help="IDD score threshold.")
def idd_check(path: str, threshold: float) -> None:
    """Check IDD scores for tasks without running evals.

    Reports per-criterion scores and provides teaching feedback
    for instructions below the threshold.
    """
    target = Path(path)
    instructions: list[tuple[str, Path]] = []

    # Collect instruction.md files
    if (target / "instruction.md").exists():
        instructions.append((_read_instruction(target), target))
    else:
        for inst_file in sorted(target.rglob("instruction.md")):
            instructions.append((_read_instruction(inst_file.parent), inst_file.parent))

    if not instructions:
        click.echo(f"No instruction.md found under {target}", err=True)
        sys.exit(1)

    below_threshold = 0

    for instruction, task_dir in instructions:
        score = score_instruction(instruction)
        passed = score.total >= threshold
        status = click.style("PASS", fg="green") if passed else click.style("FAIL", fg="red")

        click.echo(f"\n{status} {task_dir.name} (score: {score.total:.2f})")
        click.echo(f"  Goal: {score.goal.score:.2f}  Requirements: {score.requirements.score:.2f}")
        click.echo(
            f"  Constraints: {score.constraints.score:.2f}  Output: {score.output.score:.2f}"
        )
        click.echo(
            f"  Ambiguity words: {score.ambiguity_count}  Specificity: {score.specificity:.2f}"
        )

        if not passed:
            below_threshold += 1
            explanation = explain_score(score, threshold=threshold)
            click.echo(f"\n  Feedback:\n{_indent(explanation, 4)}")

    click.echo(f"\n{'=' * 40}")
    click.echo(
        f"Total: {len(instructions)} | "
        f"Passed: {len(instructions) - below_threshold} | "
        f"Failed: {below_threshold}"
    )

    if below_threshold:
        sys.exit(1)


def _read_instruction(task_dir: Path) -> str:
    """Read instruction.md from a task directory."""
    return (task_dir / "instruction.md").read_text()


def _indent(text: str, spaces: int) -> str:
    """Indent all lines of text."""
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())
