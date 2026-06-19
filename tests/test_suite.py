"""Tests for suite.yaml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from inspect_coco.suite import (
    find_suites,
    load_suite,
    merge_defaults,
)


@pytest.fixture
def suite_dir(tmp_path: Path) -> Path:
    """Create a suite directory with two tasks."""
    suite = tmp_path / "my-skill"
    suite.mkdir()

    # suite.yaml
    (suite / "suite.yaml").write_text(
        """
name: my-skill-evals
description: Test suite
skill: my-skill

defaults:
  epochs: 5
  timeout_sec: 600
  idd_threshold: 0.7

tasks: auto
"""
    )

    # Task 1
    task1 = suite / "basic"
    task1.mkdir()
    (task1 / "task.toml").write_text(
        """
version = "1.0"
[metadata]
name = "basic"
[agent]
timeout_sec = 300
"""
    )
    (task1 / "instruction.md").write_text("Do something basic.")

    # Task 2
    task2 = suite / "advanced"
    task2.mkdir()
    (task2 / "task.toml").write_text(
        """
version = "1.0"
[metadata]
name = "advanced"
epochs = 10
"""
    )
    (task2 / "instruction.md").write_text("Do something advanced.")

    return suite


@pytest.fixture
def explicit_suite_dir(tmp_path: Path) -> Path:
    """Create a suite with explicit task list."""
    suite = tmp_path / "explicit"
    suite.mkdir()

    (suite / "suite.yaml").write_text(
        """
name: explicit-suite
description: Explicit task list

defaults:
  epochs: 2

tasks:
  - path: task-a
  - path: task-b
    epochs: 7
    timeout_sec: 1200

exclude:
  - drafts
"""
    )

    for name in ("task-a", "task-b", "drafts"):
        d = suite / name
        d.mkdir()
        (d / "task.toml").write_text(f'[metadata]\nname = "{name}"\n')

    return suite


def test_load_suite_auto_discovery(suite_dir: Path) -> None:
    suite = load_suite(suite_dir)

    assert suite.name == "my-skill-evals"
    assert suite.description == "Test suite"
    assert suite.skill == "my-skill"
    assert suite.defaults.epochs == 5
    assert suite.defaults.timeout_sec == 600
    assert suite.defaults.idd_threshold == 0.7
    assert len(suite.tasks) == 2

    task_names = [t.path.name for t in suite.tasks]
    assert "basic" in task_names
    assert "advanced" in task_names


def test_load_suite_explicit_tasks(explicit_suite_dir: Path) -> None:
    suite = load_suite(explicit_suite_dir)

    assert suite.name == "explicit-suite"
    assert len(suite.tasks) == 2

    task_b = next(t for t in suite.tasks if t.path.name == "task-b")
    assert task_b.overrides == {"epochs": 7, "timeout_sec": 1200}


def test_load_suite_excludes_drafts(explicit_suite_dir: Path) -> None:
    suite = load_suite(explicit_suite_dir)
    task_names = [t.path.name for t in suite.tasks]
    assert "drafts" not in task_names


def test_load_suite_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_suite(tmp_path / "nonexistent")


def test_find_suites(tmp_path: Path) -> None:
    # Create nested suites
    (tmp_path / "a" / "suite.yaml").parent.mkdir()
    (tmp_path / "a" / "suite.yaml").write_text("name: a\n")
    (tmp_path / "b" / "suite.yaml").parent.mkdir()
    (tmp_path / "b" / "suite.yaml").write_text("name: b\n")

    suites = find_suites(tmp_path)
    assert len(suites) == 2


def test_find_suites_direct(tmp_path: Path) -> None:
    (tmp_path / "suite.yaml").write_text("name: root\ntasks: auto\n")
    suites = find_suites(tmp_path)
    assert len(suites) == 1
    assert suites[0] == tmp_path


def test_merge_defaults_task_toml_wins(suite_dir: Path) -> None:
    suite = load_suite(suite_dir)
    basic_task = next(t for t in suite.tasks if t.path.name == "basic")

    merged = merge_defaults(suite, basic_task.path)

    # task.toml specifies timeout_sec=300, overriding suite default of 600
    assert merged["timeout_sec"] == 300
    # suite default epochs=5 stays (task.toml doesn't override)
    assert merged["epochs"] == 5


def test_merge_defaults_task_epochs_override(suite_dir: Path) -> None:
    suite = load_suite(suite_dir)
    advanced_task = next(t for t in suite.tasks if t.path.name == "advanced")

    merged = merge_defaults(suite, advanced_task.path)

    # task.toml specifies epochs=10, overriding suite default of 5
    assert merged["epochs"] == 10


# --- Glob pattern tests ---


@pytest.fixture
def glob_suite_dir(tmp_path: Path) -> Path:
    """Create a suite with tasks matching glob patterns."""
    suite = tmp_path / "glob-suite"
    suite.mkdir()

    (suite / "suite.yaml").write_text(
        """
name: glob-suite
description: Tests glob patterns

tasks:
  - "basic-*"
  - path: "edge-*"
    epochs: 7

exclude:
  - drafts
"""
    )

    for name in ("basic-a", "basic-b", "edge-case", "edge-regression", "other", "drafts"):
        d = suite / name
        d.mkdir()
        (d / "task.toml").write_text(f'[metadata]\nname = "{name}"\n')

    return suite


def test_glob_pattern_matches(glob_suite_dir: Path) -> None:
    suite = load_suite(glob_suite_dir)
    task_names = [t.path.name for t in suite.tasks]

    assert "basic-a" in task_names
    assert "basic-b" in task_names
    assert "other" not in task_names


def test_glob_pattern_with_overrides(glob_suite_dir: Path) -> None:
    suite = load_suite(glob_suite_dir)

    edge_tasks = [t for t in suite.tasks if t.path.name.startswith("edge-")]
    assert len(edge_tasks) == 2
    for t in edge_tasks:
        assert t.overrides == {"epochs": 7}


def test_glob_respects_exclude(glob_suite_dir: Path) -> None:
    suite = load_suite(glob_suite_dir)
    task_names = [t.path.name for t in suite.tasks]
    assert "drafts" not in task_names


def test_glob_no_match_warns(tmp_path: Path, caplog) -> None:
    suite = tmp_path / "empty"
    suite.mkdir()

    (suite / "suite.yaml").write_text(
        """
name: no-match
tasks:
  - "nonexist-*"
"""
    )

    load_suite(suite)
    assert "No tasks matched pattern" in caplog.text
