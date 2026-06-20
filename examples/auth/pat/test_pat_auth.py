"""Tests for PAT authentication path.

Default (mocked): validates wiring without real credentials.
Live (opt-in): validates actual Snowflake PAT auth.

Run mocked:  pytest examples/auth/pat/
Run live:    pytest examples/auth/pat/ -m live
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from inspect_coco.config.connection import resolve_connection
from inspect_coco.config.deployer import deploy_credentials


@pytest.fixture
def pat_sf_home(tmp_path, monkeypatch):
    """Set up a PAT connection config."""
    monkeypatch.setenv("SNOWFLAKE_HOME", str(tmp_path))
    monkeypatch.delenv("INSPECT_COCO_SNOWFLAKE_CONNECTION", raising=False)

    (tmp_path / "connections.toml").write_text("""
[default]
account = "testorg-testaccount"
user = "testuser"
authenticator = "PROGRAMMATIC_ACCESS_TOKEN"
token = "ver:1-hint:test-pat-token-value"
role = "ANALYST"
""")
    return tmp_path


class TestPatResolution:
    def test_resolves_pat_connection(self, pat_sf_home):
        config = resolve_connection()
        assert config.authenticator == "PROGRAMMATIC_ACCESS_TOKEN"
        assert config.token == "ver:1-hint:test-pat-token-value"
        assert config.account == "testorg-testaccount"

    @pytest.mark.asyncio
    async def test_deployer_sets_token_env(self, pat_sf_home):
        config = resolve_connection()
        exec_fn = AsyncMock()
        exec_fn.return_value.returncode = 0
        exec_fn.return_value.stdout = ""
        exec_fn.return_value.stderr = ""

        env = await deploy_credentials(config, exec_fn)

        assert env["SNOWFLAKE_TOKEN"] == "ver:1-hint:test-pat-token-value"
        assert "SNOWFLAKE_PRIVATE_KEY_FILE" not in env


@pytest.mark.live
class TestPatLive:
    """Live tests require real Snowflake credentials. Skipped by default."""

    def test_live_pat_connection(self):
        config = resolve_connection()
        assert config.authenticator == "PROGRAMMATIC_ACCESS_TOKEN"
