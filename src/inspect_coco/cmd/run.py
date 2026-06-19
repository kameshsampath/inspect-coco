"""inspect-coco run — execute eval suite(s) or a single task."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import click

from inspect_coco.suite import find_suites, load_suite, merge_defaults

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

            exit_code = _invoke_inspect_eval(task_entry.path, merged, limit=limit, dry_run=dry_run)
            if exit_code != 0:
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
