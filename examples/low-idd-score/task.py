"""Low IDD score example - demonstrates IDD warning output."""

from pathlib import Path

from inspect_ai import task

from inspect_coco.tasks.loader import coco_task


@task
def low_idd_score():
    """Deliberately vague instruction to show IDD feedback."""
    return coco_task(task_dir=str(Path(__file__).parent))
