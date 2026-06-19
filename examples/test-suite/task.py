"""Test Suite example - demonstrates pytest with multiple test functions."""

from pathlib import Path

from inspect_ai import task

from inspect_coco.tasks.loader import coco_task


@task
def test_suite():
    """Multi-test eval using pytest instead of bash."""
    return coco_task(task_dir=str(Path(__file__).parent))
