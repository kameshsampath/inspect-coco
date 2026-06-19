"""inspect-coco CLI — deterministic CoCo skill evaluations.

Commands:
    inspect-coco run <path>       Run eval suite(s) or single task.
    inspect-coco idd-check <path> Check IDD scores without running evals.
    inspect-coco scaffold         Generate eval suites from plugin structure.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

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


# Register subcommands
from inspect_coco.cmd.idd_check import idd_check  # noqa: E402
from inspect_coco.cmd.run import run  # noqa: E402
from inspect_coco.cmd.scaffold import scaffold  # noqa: E402

main.add_command(run)
main.add_command(idd_check)
main.add_command(scaffold)


# Shared helpers used by multiple commands
def read_instruction(task_dir: Path) -> str:
    """Read instruction.md from a task directory."""
    return (task_dir / "instruction.md").read_text()


def indent(text: str, spaces: int) -> str:
    """Indent all lines of text."""
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def exit_with_error(message: str, code: int = 1) -> None:
    """Print error message and exit."""
    click.echo(message, err=True)
    sys.exit(code)
