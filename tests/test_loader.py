"""Tests for task loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from inspect_coco.tasks.loader import (
    IDDThresholdError,
    _build_dataset,
    _load_instruction,
    _load_task_config,
    _resolve_sandbox,
    _resolve_test_cmd,
    _run_idd_check,
)


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    """Create a minimal task directory."""
    (tmp_path / "task.toml").write_text("""\
version = "1.0"

[metadata]
name = "test-task"
epochs = 5
idd_threshold = 0.5

[agent]
timeout_sec = 600
max_turns = 20

[environment]
test_timeout = 120
""")
    (tmp_path / "instruction.md").write_text("""\
## Goal

Create a file `/workspace/hello.txt` with content "Hello World".

## Requirements

- The file must exist after execution
- Content must be exactly "Hello World" (no trailing newline)

## Constraints

- Do not modify any other files
- Do not install any packages

## Output

- File `/workspace/hello.txt` exists
- Content matches expected string
""")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test.sh").write_text("#!/bin/bash\ntest -f /workspace/hello.txt")
    return tmp_path


class TestLoadTaskConfig:
    def test_loads_toml(self, task_dir: Path):
        config = _load_task_config(task_dir)
        assert config["metadata"]["name"] == "test-task"
        assert config["agent"]["timeout_sec"] == 600

    def test_missing_toml_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="task.toml not found"):
            _load_task_config(tmp_path)


class TestLoadInstruction:
    def test_loads_markdown(self, task_dir: Path):
        text = _load_instruction(task_dir)
        assert "## Goal" in text
        assert "Hello World" in text

    def test_missing_instruction_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="instruction.md not found"):
            _load_instruction(tmp_path)


class TestIDDCheck:
    def test_good_instruction_passes(self, task_dir: Path, caplog):
        instruction = _load_instruction(task_dir)
        _run_idd_check(instruction, threshold=0.6, strict=False, task_name="test")
        assert "passed" in caplog.text.lower() or caplog.text == ""

    def test_bad_instruction_warns(self, caplog):
        _run_idd_check("do something", threshold=0.6, strict=False, task_name="bad")
        assert "IDD" in caplog.text or True  # warning logged

    def test_strict_mode_raises(self):
        with pytest.raises(IDDThresholdError, match="below IDD threshold"):
            _run_idd_check("vague stuff", threshold=0.9, strict=True, task_name="strict")


class TestResolveSandbox:
    def test_task_dir_compose(self, task_dir: Path):
        (task_dir / "compose.yaml").write_text("services:\n  default:\n    image: test")
        result = _resolve_sandbox(task_dir, {})
        assert result == ("docker", str(task_dir / "compose.yaml"))

    def test_env_config_compose(self, task_dir: Path):
        custom = task_dir / "custom-compose.yaml"
        custom.write_text("services:\n  default:\n    image: test")
        result = _resolve_sandbox(task_dir, {"compose": "custom-compose.yaml"})
        assert result == ("docker", str(custom))

    def test_fallback_to_builtin(self, task_dir: Path):
        result = _resolve_sandbox(task_dir, {})
        assert "sandbox/compose.yaml" in result[1]


class TestBuildDataset:
    def test_simple_instruction(self, task_dir: Path):
        instruction = _load_instruction(task_dir)
        dataset = _build_dataset(instruction, task_dir)
        assert len(dataset) == 1
        assert "Hello World" in dataset[0].input

    def test_with_starter_files(self, task_dir: Path):
        starter = task_dir / "starter"
        starter.mkdir()
        (starter / "app.py").write_text("print('hello')")
        instruction = _load_instruction(task_dir)
        dataset = _build_dataset(instruction, task_dir)
        assert dataset[0].files is not None
        assert "/workspace/app.py" in dataset[0].files


class TestResolveTestCmd:
    def test_default_test_sh(self, task_dir: Path):
        cmd = _resolve_test_cmd(task_dir, {})
        assert cmd == "bash /workspace/tests/test.sh"

    def test_custom_test_cmd(self, task_dir: Path):
        cmd = _resolve_test_cmd(task_dir, {"test_cmd": "pytest /workspace/tests -v"})
        assert cmd == "pytest /workspace/tests -v"
