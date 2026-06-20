"""Token refresh integration test.

Starts the token proxy, polls it over a period that exceeds the access token
TTL (~10 min), and verifies that a token rotation (refresh) occurs.

Run with:
    pytest -m live tests/integration/test_token_refresh.py -v --timeout=1000

This test requires:
    - A valid OAuth connection configured (INSPECT_COCO_SNOWFLAKE_CONNECTION)
    - ~12 minutes to run (polls every 60s for 12 iterations)
"""

from __future__ import annotations

import json
import logging
import time
from urllib.request import Request, urlopen

import pytest

from inspect_coco.config.connection import resolve_connection
from inspect_coco.proxy.server import TokenProxy

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.live

POLL_INTERVAL_SEC = 60
POLL_ITERATIONS = 12  # 12 minutes total


@pytest.fixture(scope="module")
def running_proxy():
    """Start the token proxy using the real configured connection."""
    config = resolve_connection()
    if config.authenticator != "OAUTH_AUTHORIZATION_CODE":
        pytest.skip("Requires OAUTH_AUTHORIZATION_CODE authenticator")

    proxy = TokenProxy(account=config.account, role=config.role)
    proxy.start()
    yield proxy
    proxy.stop()


def test_token_refresh_during_long_run(running_proxy):
    """Verify that the proxy refreshes the access token over a 12-minute window."""
    proxy = running_proxy
    url = f"{proxy.url}/token"

    tokens_seen: list[str] = []
    log: list[dict] = []

    for i in range(POLL_ITERATIONS):
        resp = urlopen(Request(url))
        data = json.loads(resp.read())

        token = data["access_token"]
        expires_in = data["expires_in"]
        is_new = token not in tokens_seen

        if is_new:
            tokens_seen.append(token)

        entry = {
            "iteration": i + 1,
            "elapsed_min": i,
            "expires_in_sec": expires_in,
            "token_changed": is_new,
            "unique_tokens_so_far": len(tokens_seen),
        }
        log.append(entry)
        logger.info(
            "Poll %d/%d: expires_in=%ds, changed=%s, unique_tokens=%d",
            i + 1,
            POLL_ITERATIONS,
            expires_in,
            is_new,
            len(tokens_seen),
        )

        if i < POLL_ITERATIONS - 1:
            time.sleep(POLL_INTERVAL_SEC)

    # At least 2 unique tokens means a refresh happened
    refresh_detected = len(tokens_seen) >= 2
    logger.info(
        "Result: %d unique tokens seen over %d minutes. Refresh detected: %s",
        len(tokens_seen),
        POLL_ITERATIONS,
        refresh_detected,
    )

    assert refresh_detected, (
        f"Expected at least one token refresh in {POLL_ITERATIONS} minutes, "
        f"but only saw {len(tokens_seen)} unique token(s). "
        f"Log: {json.dumps(log, indent=2)}"
    )
