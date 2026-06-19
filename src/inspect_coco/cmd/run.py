"""inspect-coco run — execute eval suite(s) or a single task."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from inspect_coco.suite import find_suites, load_suite, merge_defaults
from inspect_coco.tasks.loader import coco_task

logger = logging.getLogger(__name__)


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--task",
    "single_task",
    type=click.Path(exists=True),
    help="Run a single task directory.",
)
@click.option("--epochs", type=int, help="Override epochs (pass@k).")
@click.option("--model", type=str, help="Override CoCo model.")
@click.option("-c", "--connection", type=str, help="Override Snowflake connection name.")
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
            target,
            epochs=epochs,
            model=model,
            connection=connection,
            limit=limit,
            dry_run=dry_run,
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

            success = _eval_task(task_entry.path, merged, limit=limit, dry_run=dry_run)
            if not success:
                failed += 1

    if failed:
        click.echo(f"\n{failed} task(s) failed.", err=True)
        sys.exit(1)

    click.echo("\nAll tasks completed successfully.")


def _run_single_task(
    task_dir: Path,
    epochs: int | None = None,
    model: str | None = None,
    connection: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Run a single task directory."""
    config: dict = {}
    if epochs is not None:
        config["epochs"] = epochs
    if model is not None:
        config["model"] = model
    if connection is not None:
        config["connection"] = connection

    success = _eval_task(task_dir, config, limit=limit, dry_run=dry_run)
    if not success:
        sys.exit(1)


def _eval_task(
    task_dir: Path, config: dict, limit: int | None = None, dry_run: bool = False
) -> bool:
    """Build a Task and run it via inspect_ai.eval() in-process.

    Returns True on success, False on failure.
    """
    from inspect_ai import eval as inspect_eval

    if not (task_dir / "task.toml").exists():
        click.echo(f"  SKIP {task_dir.name} (no task.toml)", err=True)
        return True

    click.echo(f"  {'[DRY-RUN] ' if dry_run else ''}Running: {task_dir.name}")

    if dry_run:
        click.echo(f"    task_dir={task_dir}")
        click.echo(f"    config={config}")
        if limit:
            click.echo(f"    limit={limit}")
        return True

    # Build the Task object directly (no task.py needed)
    task_obj = coco_task(
        task_dir=str(task_dir),
        timeout_sec=config.get("timeout_sec", 900),
        epochs=config.get("epochs"),
        idd_threshold=config.get("idd_threshold"),
        idd_strict=config.get("idd_strict", False),
    )

    # Call Inspect's eval() API in-process
    eval_kwargs: dict = {}
    if limit is not None:
        eval_kwargs["limit"] = limit

    try:
        logs = inspect_eval(
            tasks=task_obj,
            **eval_kwargs,
        )
    except Exception as e:
        click.echo(f"  FAILED {task_dir.name}: {e}", err=True)
        logger.exception("Eval failed for %s", task_dir.name)
        return False

    # Check results
    for log in logs:
        if log.status == "error":
            click.echo(f"  FAILED {task_dir.name}: {log.error}", err=True)
            return False

    return True
