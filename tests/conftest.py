"""Shared test fixtures."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _disable_keyring_in_tests(request):
    """Disable keyring in non-live tests to use file-based fallback.

    Live tests (marked with @pytest.mark.live) use the real keyring
    since they need actual OS credentials.
    """
    if "live" in [mark.name for mark in request.node.iter_markers()]:
        yield
    else:
        with patch("inspect_coco.config.oauth._use_keyring", return_value=False):
            yield
