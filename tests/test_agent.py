"""Tests for CoCo agent command building and prompt extraction."""

from __future__ import annotations

from inspect_coco.agents.cortex_code import _build_command, _extract_prompt


class TestBuildCommand:
    def test_minimal_command(self):
        cmd = _build_command("Hello world", model_name=None, skills=None)
        assert cmd == [
            "cortex",
            "--print",
            "Hello world",
            "--dangerously-allow-all-tool-calls",
            "--output-format",
            "stream-json",
        ]

    def test_with_model(self):
        cmd = _build_command("test", model_name="claude-sonnet-4-5", skills=None)
        assert "--model" in cmd
        assert "claude-sonnet-4-5" in cmd

    def test_with_skills(self):
        cmd = _build_command("test", model_name=None, skills=["/path/skill.md", "/other.md"])
        assert cmd.count("--skill") == 2
        assert "/path/skill.md" in cmd
        assert "/other.md" in cmd

    def test_with_all_options(self):
        cmd = _build_command(
            "do something",
            model_name="claude-opus-4-5",
            skills=["/s1.md"],
        )
        assert "do something" in cmd
        assert "claude-opus-4-5" in cmd
        assert "/s1.md" in cmd


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
