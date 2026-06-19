"""Fix Syntax Errors eval task."""

from pathlib import Path

from inspect_ai import task

from inspect_coco.tasks.loader import coco_task


@task
def fix_syntax_errors():
    """Code repair eval - fix broken Python."""
    return coco_task(task_dir=str(Path(__file__).parent))
