"""Hello World eval task."""

from pathlib import Path

from inspect_ai import task

from inspect_coco.tasks.loader import coco_task


@task
def hello_world():
    """Simple file creation eval."""
    return coco_task(task_dir=str(Path(__file__).parent))
