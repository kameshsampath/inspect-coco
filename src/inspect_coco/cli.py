"""CLI for inspect-coco.

Commands:
    inspect-coco run <path>       Run eval suite(s) or single task.
    inspect-coco idd-check <path> Check IDD scores without running evals.
    inspect-coco scaffold         Generate eval suites from plugin structure.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import click

from inspect_coco.idd import explain_score, score_instruction
from inspect_coco.suite import find_suites, load_suite, merge_defaults

logger = logging.getLogger(__name__)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """inspect-coco: deterministic CoCo skill evaluations."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--task", "single_task", type=click.Path(exists=True), help="Run a single task directory."
)
@click.option("--epochs", type=int, help="Override epochs (pass@k).")
@click.option("--model", type=str, help="Override CoCo model.")
@click.option("--connection", type=str, help="Override Snowflake connection name.")
@click.option("--limit", type=int, help="Limit samples per task (for quick tests).")
@click.option("--dry-run", is_flag=True, help="Show what would run without executing.")
def run(
    path: str,
    single_task: str | None,
    epochs: int | None,
    model: str | None,
    connection: str | None,
    limit: int | None,
    dry_run: bool,
) -> None:
    """Run eval suite(s) or a single task.

    PATH can be a suite directory (containing suite.yaml), a parent
    directory to search recursively, or a single task directory.
    """
    target = Path(path)

    if single_task:
        _run_single_task(
            Path(single_task),
            epochs=epochs,
            model=model,
            connection=connection,
            limit=limit,
            dry_run=dry_run,
        )
        return

    # Check if path is a task directory (has task.toml but no suite.yaml)
    if (target / "task.toml").exists() and not (target / "suite.yaml").exists():
        _run_single_task(
            target, epochs=epochs, model=model, connection=connection, limit=limit, dry_run=dry_run
        )
        return

    # Find and run suites
    suites = find_suites(target)
    if not suites:
        click.echo(f"No suite.yaml found under {target}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(suites)} suite(s)")
    failed = 0

    for suite_dir in suites:
        suite = load_suite(suite_dir)
        click.echo(f"\n{'=' * 60}")
        click.echo(f"Suite: {suite.name}")
        if suite.description:
            click.echo(f"  {suite.description}")
        click.echo(f"  Tasks: {len(suite.tasks)}")
        click.echo(f"{'=' * 60}")

        for task_entry in suite.tasks:
            merged = merge_defaults(suite, task_entry.path)

            # Apply CLI overrides (highest priority)
            if epochs is not None:
                merged["epochs"] = epochs
            if model is not None:
                merged["model"] = model
            if connection is not None:
                merged["connection"] = connection

            exit_code = _invoke_inspect_eval(task_entry.path, merged, limit=limit, dry_run=dry_run)
            if exit_code != 0:
                failed += 1

    if failed:
        click.echo(f"\n{failed} task(s) failed.", err=True)
        sys.exit(1)

    click.echo("\nAll tasks completed successfully.")


@main.command("idd-check")
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
        f"Total: {len(instructions)} | Passed: {len(instructions) - below_threshold} | Failed: {below_threshold}"
    )

    if below_threshold:
        sys.exit(1)


@main.command()
@click.option(
    "--plugin-dir",
    type=click.Path(exists=True),
    help="Skills directory to scan (default: auto-detect from .cortex-plugin/plugin.json).",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="evals",
    help="Output directory for generated eval suites.",
)
@click.option(
    "--skill", "only_skills", multiple=True, help="Only scaffold these skills (repeatable)."
)
@click.option(
    "--ignore", "extra_ignores", multiple=True, help="Extra ignore patterns (repeatable)."
)
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing.")
def scaffold(
    plugin_dir: str | None,
    output_dir: str,
    only_skills: tuple[str, ...],
    extra_ignores: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Generate eval suites from CoCo plugin/skill structure.

    Scans the current project for CoCo skills, filters out routers
    and ignored paths, and generates IDD-structured eval tasks.
    """
    from inspect_coco.scaffold import detect_plugin, filter_skills, generate_suite

    root = Path.cwd()
    plugin_path = Path(plugin_dir) if plugin_dir else None
    out = Path(output_dir)

    # Detect skills
    skills = detect_plugin(root, plugin_dir=plugin_path)
    if not skills:
        click.echo(
            "No skills found. Ensure .cortex-plugin/plugin.json exists or use --plugin-dir.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Detected {len(skills)} skill(s)")

    # Filter
    filtered = filter_skills(
        skills,
        project_root=root,
        extra_ignores=list(extra_ignores) if extra_ignores else None,
        only_skills=list(only_skills) if only_skills else None,
    )

    if not filtered:
        click.echo("No leaf skills remain after filtering (all routers or ignored).", err=True)
        sys.exit(1)

    click.echo(f"Generating evals for {len(filtered)} leaf skill(s):")
    for s in filtered:
        click.echo(f"  - {s.name}")

    # Generate
    all_files: list[Path] = []
    for skill in filtered:
        files = generate_suite(skill, output_dir=out, dry_run=dry_run)
        all_files.extend(files)

    if dry_run:
        click.echo(f"\n[DRY-RUN] Would create {len(all_files)} files:")
        for f in all_files:
            click.echo(f"  {f}")
        return

    click.echo(f"\nGenerated {len(all_files)} files in {out}/")

    # Run IDD check on generated instructions
    click.echo("\nIDD score check on generated instructions:")
    for skill in filtered:
        inst_path = out / skill.name / "basic-prompt" / "instruction.md"
        if inst_path.exists():
            score = score_instruction(inst_path.read_text())
            status = (
                click.style("PASS", fg="green")
                if score.total >= 0.6
                else click.style("WARN", fg="yellow")
            )
            click.echo(f"  {status} {skill.name}: {score.total:.2f}")

    click.echo("\nDone. Next steps:")
    click.echo("  1. Edit tests/test.sh in each task to add verification logic")
    click.echo("  2. Refine instruction.md Output section with specific success criteria")
    click.echo(f"  3. Run: inspect-coco idd-check {out}/")
    click.echo(f"  4. Run: inspect-coco run {out}/ --dry-run")


def _run_single_task(
    task_dir: Path,
    epochs: int | None = None,
    model: str | None = None,
    connection: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Run a single task directory through inspect eval."""
    config: dict = {}
    if epochs is not None:
        config["epochs"] = epochs
    if model is not None:
        config["model"] = model
    if connection is not None:
        config["connection"] = connection

    exit_code = _invoke_inspect_eval(task_dir, config, limit=limit, dry_run=dry_run)
    if exit_code != 0:
        sys.exit(exit_code)


def _invoke_inspect_eval(
    task_dir: Path, config: dict, limit: int | None = None, dry_run: bool = False
) -> int:
    """Build and invoke `inspect eval` command for a task."""
    task_py = task_dir / "task.py"
    if not task_py.exists():
        click.echo(f"  SKIP {task_dir.name} (no task.py)", err=True)
        return 0

    cmd = ["inspect", "eval", str(task_py)]

    # Pass configuration as -T params
    if config.get("epochs"):
        cmd.extend(["-T", f"epochs={config['epochs']}"])
    if config.get("timeout_sec"):
        cmd.extend(["-T", f"timeout_sec={config['timeout_sec']}"])
    if config.get("idd_threshold"):
        cmd.extend(["-T", f"idd_threshold={config['idd_threshold']}"])
    if config.get("idd_strict"):
        cmd.extend(["-T", f"idd_strict={config['idd_strict']}"])

    if limit is not None:
        cmd.extend(["--limit", str(limit)])

    click.echo(f"  {'[DRY-RUN] ' if dry_run else ''}Running: {task_dir.name}")
    logger.debug("Command: %s", " ".join(cmd))

    if dry_run:
        click.echo(f"    {' '.join(cmd)}")
        return 0

    result = subprocess.run(cmd, cwd=str(task_dir))
    return result.returncode


def _read_instruction(task_dir: Path) -> str:
    """Read instruction.md from a task directory."""
    return (task_dir / "instruction.md").read_text()


def _indent(text: str, spaces: int) -> str:
    """Indent all lines of text."""
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


if __name__ == "__main__":
    main()
