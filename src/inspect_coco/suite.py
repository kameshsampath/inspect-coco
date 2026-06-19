"""Suite configuration loader for inspect-coco.

A suite.yaml defines shared defaults for all eval scenarios within a skill.
Each skill's eval directory gets its own suite.yaml.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

SUITE_FILENAME = "suite.yaml"


@dataclass
class SuiteDefaults:
    """Shared defaults for all tasks in a suite."""

    epochs: int = 3
    timeout_sec: int = 900
    max_turns: int | None = None
    idd_threshold: float = 0.6
    idd_strict: bool = False
    model: str | None = None
    connection: str | None = None


@dataclass
class TaskEntry:
    """A task within a suite (discovered or explicit)."""

    path: Path
    overrides: dict = field(default_factory=dict)


@dataclass
class Suite:
    """Parsed suite configuration."""

    name: str
    description: str
    skill: str | None
    defaults: SuiteDefaults
    tasks: list[TaskEntry]
    root: Path  # directory containing suite.yaml


def load_suite(suite_path: Path) -> Suite:
    """Load a suite.yaml file and discover tasks.

    Args:
        suite_path: Path to a directory containing suite.yaml,
                    or path to the suite.yaml file itself.

    Returns:
        Parsed Suite with discovered tasks.
    """
    if suite_path.is_file():
        suite_file = suite_path
        root = suite_path.parent
    else:
        suite_file = suite_path / SUITE_FILENAME
        root = suite_path

    if not suite_file.exists():
        raise FileNotFoundError(f"No {SUITE_FILENAME} found in {root}")

    with open(suite_file) as f:
        data = yaml.safe_load(f) or {}

    # Parse defaults
    defaults_data = data.get("defaults", {})
    defaults = SuiteDefaults(
        epochs=defaults_data.get("epochs", 3),
        timeout_sec=defaults_data.get("timeout_sec", 900),
        max_turns=defaults_data.get("max_turns"),
        idd_threshold=defaults_data.get("idd_threshold", 0.6),
        idd_strict=defaults_data.get("idd_strict", False),
        model=defaults_data.get("model"),
        connection=defaults_data.get("connection"),
    )

    # Discover or parse tasks
    tasks_config = data.get("tasks", "auto")
    exclude = data.get("exclude", [])

    if tasks_config == "auto":
        tasks = _auto_discover_tasks(root, exclude)
    else:
        tasks = _parse_explicit_tasks(root, tasks_config, exclude)

    return Suite(
        name=data.get("name", root.name),
        description=data.get("description", ""),
        skill=data.get("skill"),
        defaults=defaults,
        tasks=tasks,
        root=root,
    )


def find_suites(search_path: Path) -> list[Path]:
    """Find all suite.yaml files under a directory.

    Args:
        search_path: Directory to search recursively.

    Returns:
        List of paths to directories containing suite.yaml.
    """
    suites = []
    if (search_path / SUITE_FILENAME).exists():
        suites.append(search_path)
    else:
        for suite_file in sorted(search_path.rglob(SUITE_FILENAME)):
            suites.append(suite_file.parent)
    return suites


def merge_defaults(suite: Suite, task_path: Path) -> dict:
    """Merge suite defaults with task.toml to produce final config.

    Priority: task.toml > suite per-task overrides > suite defaults > built-in

    Args:
        suite: The loaded suite configuration.
        task_path: Path to the task directory.

    Returns:
        Merged configuration dict for coco_task().
    """
    import toml as toml_lib

    # Start with suite defaults
    merged = {
        "epochs": suite.defaults.epochs,
        "timeout_sec": suite.defaults.timeout_sec,
        "idd_threshold": suite.defaults.idd_threshold,
        "idd_strict": suite.defaults.idd_strict,
    }
    if suite.defaults.max_turns:
        merged["max_turns"] = suite.defaults.max_turns
    if suite.defaults.model:
        merged["model"] = suite.defaults.model
    if suite.defaults.connection:
        merged["connection"] = suite.defaults.connection

    # Apply per-task overrides from suite.yaml tasks list
    for task_entry in suite.tasks:
        if task_entry.path == task_path:
            merged.update(task_entry.overrides)
            break

    # Apply task.toml values (highest priority)
    toml_path = task_path / "task.toml"
    if toml_path.exists():
        task_config = toml_lib.load(toml_path)
        metadata = task_config.get("metadata", {})
        agent = task_config.get("agent", {})

        if "epochs" in metadata:
            merged["epochs"] = metadata["epochs"]
        if "idd_threshold" in metadata:
            merged["idd_threshold"] = metadata["idd_threshold"]
        if "idd_strict" in metadata:
            merged["idd_strict"] = metadata["idd_strict"]
        if "timeout_sec" in agent:
            merged["timeout_sec"] = agent["timeout_sec"]
        if "max_turns" in agent:
            merged["max_turns"] = agent["max_turns"]
        if "model" in agent:
            merged["model"] = agent["model"]
        if "connection" in agent:
            merged["connection"] = agent["connection"]

    return merged


def _auto_discover_tasks(root: Path, exclude: list[str]) -> list[TaskEntry]:
    """Auto-discover task directories (contain task.toml)."""
    tasks = []
    for task_toml in sorted(root.rglob("task.toml")):
        task_dir = task_toml.parent
        # Skip if task_dir IS the suite root (suite.yaml + task.toml at same level)
        if task_dir == root:
            continue
        # Check exclude patterns
        rel_path = str(task_dir.relative_to(root))
        if any(rel_path.startswith(exc.rstrip("/")) for exc in exclude):
            continue
        tasks.append(TaskEntry(path=task_dir))

    if not tasks:
        logger.warning("No tasks discovered in %s", root)

    return tasks


def _parse_explicit_tasks(
    root: Path, tasks_config: list[dict], exclude: list[str]
) -> list[TaskEntry]:
    """Parse explicit task list from suite.yaml.

    Supports both literal paths and fnmatch patterns (e.g., 'basic-*').
    Patterns are matched against all task directories found under root.
    """
    tasks = []
    for entry in tasks_config:
        if isinstance(entry, str):
            pattern = entry
            overrides = {}
        elif isinstance(entry, dict):
            pattern = entry["path"]
            overrides = {k: v for k, v in entry.items() if k != "path"}
        else:
            continue

        if _has_glob_chars(pattern):
            matched = _match_pattern(root, pattern, exclude)
            for task_dir in matched:
                tasks.append(TaskEntry(path=task_dir, overrides=overrides.copy()))
            if not matched:
                logger.warning("No tasks matched pattern '%s' in %s", pattern, root)
        else:
            path = root / pattern
            rel_path = str(path.relative_to(root))
            if any(rel_path.startswith(exc.rstrip("/")) for exc in exclude):
                continue
            if path.exists():
                tasks.append(TaskEntry(path=path, overrides=overrides))
            else:
                logger.warning("Task path not found: %s", path)

    return tasks


def _has_glob_chars(s: str) -> bool:
    """Check if a string contains fnmatch glob metacharacters."""
    return any(c in s for c in ("*", "?", "["))


def _match_pattern(root: Path, pattern: str, exclude: list[str]) -> list[Path]:
    """Match an fnmatch pattern against all task directories under root."""
    matched = []
    for task_toml in sorted(root.rglob("task.toml")):
        task_dir = task_toml.parent
        if task_dir == root:
            continue
        rel_path = str(task_dir.relative_to(root))
        if any(rel_path.startswith(exc.rstrip("/")) for exc in exclude):
            continue
        if fnmatch.fnmatch(rel_path, pattern):
            matched.append(task_dir)
    return matched
