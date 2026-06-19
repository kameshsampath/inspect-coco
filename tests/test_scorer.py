"""Tests for verification scorer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inspect_coco.scorers.verification import passed, total, verification


class TestVerificationScorer:
    @pytest.mark.asyncio
    async def test_passing_test(self):
        scorer_fn = verification(test_cmd="echo pass")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed in 0.5s"
        mock_result.stderr = ""

        mock_state = MagicMock()
        mock_state.output = MagicMock()
        mock_state.output.completion = "agent did the thing"

        mock_target = MagicMock()

        with patch("inspect_coco.scorers.verification.sandbox") as mock_sandbox:
            mock_sandbox.return_value.exec = AsyncMock(return_value=mock_result)
            score = await scorer_fn(mock_state, mock_target)

        assert score.value == 1.0
        assert "3 passed" in score.explanation

    @pytest.mark.asyncio
    async def test_failing_test(self):
        scorer_fn = verification(test_cmd="pytest /workspace/tests")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "FAILED test_output.py::test_file_exists - AssertionError"

        mock_state = MagicMock()
        mock_state.output = MagicMock()
        mock_state.output.completion = ""

        mock_target = MagicMock()

        with patch("inspect_coco.scorers.verification.sandbox") as mock_sandbox:
            mock_sandbox.return_value.exec = AsyncMock(return_value=mock_result)
            score = await scorer_fn(mock_state, mock_target)

        assert score.value == 0.0
        assert "EXIT 1" in score.explanation
        assert "AssertionError" in score.explanation

    @pytest.mark.asyncio
    async def test_custom_test_cmd(self):
        scorer_fn = verification(test_cmd="bash /custom/verify.sh", timeout=60)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OK"
        mock_result.stderr = ""

        mock_state = MagicMock()
        mock_state.output = MagicMock()
        mock_state.output.completion = "done"

        mock_target = MagicMock()

        with patch("inspect_coco.scorers.verification.sandbox") as mock_sandbox:
            mock_sandbox.return_value.exec = AsyncMock(return_value=mock_result)
            score = await scorer_fn(mock_state, mock_target)

            call_args = mock_sandbox.return_value.exec.call_args
            assert "bash /custom/verify.sh" in call_args.kwargs["cmd"][2]
            assert call_args.kwargs["timeout"] == 60

        assert score.value == 1.0


class TestMetrics:
    def test_passed_metric(self):
        metric_fn = passed()
        scores = [
            MagicMock(value=1.0),
            MagicMock(value=0.0),
            MagicMock(value=1.0),
        ]
        assert metric_fn(scores) == 2

    def test_total_metric(self):
        metric_fn = total()
        scores = [
            MagicMock(value=1.0),
            MagicMock(value=0.0),
            MagicMock(value=1.0),
        ]
        assert metric_fn(scores) == 3

    def test_passed_empty(self):
        metric_fn = passed()
        assert metric_fn([]) == 0

    def test_total_empty(self):
        metric_fn = total()
        assert metric_fn([]) == 0
