"""Tests for CoCo agent command building and prompt extraction."""

from __future__ import annotations

from inspect_coco.agents.coco import _build_command, _extract_prompt


class TestBuildCommand:
    def test_minimal_command(self):
        cmd = _build_command("/tmp/prompt.md", model_name=None)
        assert cmd == [
            "cortex",
            "exec",
            "--file",
            "/tmp/prompt.md",
            "--format",
            "json",
            "--bypass",
            "--no-history",
        ]

    def test_with_model(self):
        cmd = _build_command("/tmp/p.md", model_name="claude-sonnet-4-5")
        assert "--model" in cmd
        assert "claude-sonnet-4-5" in cmd

    def test_with_max_turns(self):
        cmd = _build_command("/tmp/p.md", model_name=None, max_turns=30)
        assert "--max-turns" in cmd
        assert "30" in cmd

    def test_with_connection(self):
        cmd = _build_command("/tmp/p.md", model_name=None, connection_name="prod")
        assert "--connection" in cmd
        assert "prod" in cmd

    def test_with_workdir(self):
        cmd = _build_command("/tmp/p.md", model_name=None, workdir="/workspace")
        assert "--workdir" in cmd
        assert "/workspace" in cmd

    def test_with_all_options(self):
        cmd = _build_command(
            "/tmp/p.md",
            model_name="claude-opus-4-5",
            max_turns=50,
            connection_name="eval",
            workdir="/project",
        )
        assert "--file" in cmd
        assert "/tmp/p.md" in cmd
        assert "claude-opus-4-5" in cmd
        assert "50" in cmd
        assert "eval" in cmd
        assert "/project" in cmd


class TestExtractPrompt:
    def test_simple_user_message(self):
        from unittest.mock import MagicMock

        state = MagicMock()
        msg = MagicMock()
        msg.role = "user"
        msg.content = "What is 2+2?"
        state.messages = [msg]

        result = _extract_prompt(state)
        assert result == "What is 2+2?"

    def test_last_user_message_used(self):
        from unittest.mock import MagicMock

        state = MagicMock()
        msg1 = MagicMock()
        msg1.role = "user"
        msg1.content = "first"

        msg2 = MagicMock()
        msg2.role = "assistant"
        msg2.content = "response"

        msg3 = MagicMock()
        msg3.role = "user"
        msg3.content = "second"

        state.messages = [msg1, msg2, msg3]

        result = _extract_prompt(state)
        assert result == "second"

    def test_empty_messages(self):
        from unittest.mock import MagicMock

        state = MagicMock()
        state.messages = []

        result = _extract_prompt(state)
        assert result == ""
