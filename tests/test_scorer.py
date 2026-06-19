"""Tests for scorers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inspect_coco.scorers.pytest_scorer import pytest_scorer


class TestPytestScorer:
    @pytest.mark.asyncio
    async def test_passing_test(self):
        scorer_fn = pytest_scorer(test_cmd="echo pass")

        # Mock sandbox exec
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed in 0.5s"
        mock_result.stderr = ""

        mock_state = MagicMock()
        mock_state.output = MagicMock()
        mock_state.output.completion = "agent did the thing"

        mock_target = MagicMock()

        with patch("inspect_coco.scorers.pytest_scorer.sandbox") as mock_sandbox:
            mock_sandbox.return_value.exec = AsyncMock(return_value=mock_result)
            score = await scorer_fn(mock_state, mock_target)

        assert score.value == 1.0
        assert "3 passed" in score.explanation

    @pytest.mark.asyncio
    async def test_failing_test(self):
        scorer_fn = pytest_scorer(test_cmd="pytest /workspace/tests")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "FAILED test_output.py::test_file_exists - AssertionError"

        mock_state = MagicMock()
        mock_state.output = MagicMock()
        mock_state.output.completion = ""

        mock_target = MagicMock()

        with patch("inspect_coco.scorers.pytest_scorer.sandbox") as mock_sandbox:
            mock_sandbox.return_value.exec = AsyncMock(return_value=mock_result)
            score = await scorer_fn(mock_state, mock_target)

        assert score.value == 0.0
        assert "EXIT 1" in score.explanation
        assert "AssertionError" in score.explanation

    @pytest.mark.asyncio
    async def test_custom_test_cmd(self):
        scorer_fn = pytest_scorer(test_cmd="bash /custom/verify.sh", timeout=60)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_result.stderr = ""

        mock_state = MagicMock()
        mock_state.output = MagicMock()
        mock_state.output.completion = "done"

        mock_target = MagicMock()

        with patch("inspect_coco.scorers.pytest_scorer.sandbox") as mock_sandbox:
            mock_sandbox.return_value.exec = AsyncMock(return_value=mock_result)
            score = await scorer_fn(mock_state, mock_target)

            # Verify correct command was used
            call_args = mock_sandbox.return_value.exec.call_args
            assert "bash /custom/verify.sh" in call_args.kwargs["cmd"][2]
            assert call_args.kwargs["timeout"] == 60

        assert score.value == 1.0
