"""Integration tests for the host-process token proxy with Docker sandbox.

These tests require Docker and verify that:
1. The token proxy starts on a random port on the host
2. The sandbox container can reach the proxy via extra_hosts (host-gateway)
3. The proxy serves valid tokens

Run with: pytest -m docker tests/integration/test_proxy_compose.py
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from inspect_coco.proxy.server import TokenProxy

SANDBOX_DIR = Path(__file__).parent.parent.parent / "src/inspect_coco/sandbox"
COMPOSE_FILE = SANDBOX_DIR / "compose.yaml"


pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def token_cache(tmp_path_factory):
    """Create a temporary OAuth token cache for testing."""
    cache_dir = tmp_path_factory.mktemp("snowflake")
    cache_file = cache_dir / "inspect-coco-oauth.json"
    cache_file.write_text(
        json.dumps(
            {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": time.time() + 3600,
                "account": "test-account",
                "role": "ANALYST",
            }
        )
    )
    return cache_dir


@pytest.fixture(scope="module")
def proxy_and_sandbox(token_cache):
    """Start the token proxy on host and sandbox container."""
    # Patch keyring to use file fallback with our temp cache
    with patch("inspect_coco.config.oauth._use_keyring", return_value=False):
        with patch("inspect_coco.config.oauth.snowflake_home", return_value=token_cache):
            proxy = TokenProxy(account="test-account")
            proxy.start()

    env = {
        **os.environ,
        "TOKEN_PROXY_PORT": str(proxy.port),
    }

    # Start sandbox
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "--project-directory",
            str(SANDBOX_DIR),
            "up",
            "-d",
            "--pull",
            "missing",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    if result.returncode != 0:
        proxy.stop()
        pytest.skip(f"Failed to start sandbox: {result.stderr}")

    yield {"env": env, "proxy": proxy}

    # Tear down
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "--project-directory",
            str(SANDBOX_DIR),
            "down",
            "-v",
            "--remove-orphans",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    proxy.stop()


class TestHostProxy:
    def test_sandbox_can_reach_proxy(self, proxy_and_sandbox):
        """Sandbox container can fetch tokens from the host proxy via host-gateway."""
        env = proxy_and_sandbox["env"]
        port = proxy_and_sandbox["proxy"].port

        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "--project-directory",
                str(SANDBOX_DIR),
                "exec",
                "default",
                "python",
                "-c",
                (
                    "import urllib.request, json; "
                    f"resp = urllib.request.urlopen('http://token-proxy:{port}/token'); "
                    "data = json.loads(resp.read()); "
                    "print(json.dumps(data))"
                ),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        data = json.loads(result.stdout.strip())
        assert "access_token" in data
        assert data["token_type"] == "Bearer"

    def test_proxy_health_from_sandbox(self, proxy_and_sandbox):
        """Health endpoint reachable from sandbox."""
        env = proxy_and_sandbox["env"]
        port = proxy_and_sandbox["proxy"].port

        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "--project-directory",
                str(SANDBOX_DIR),
                "exec",
                "default",
                "python",
                "-c",
                (
                    "import urllib.request, json; "
                    f"resp = urllib.request.urlopen('http://token-proxy:{port}/health'); "
                    "data = json.loads(resp.read()); "
                    "print(data['status'])"
                ),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        assert result.returncode == 0
        assert result.stdout.strip() == "ok"
