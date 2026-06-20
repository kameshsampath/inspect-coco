"""Tests for OAuth authentication path (host-process token proxy).

Default (mocked): validates wiring without real credentials.
Live (opt-in): validates actual Snowflake OAuth auth + proxy.

Run mocked:  pytest examples/auth/oauth/
Run live:    pytest examples/auth/oauth/ -m live
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from inspect_coco.config.connection import resolve_connection
from inspect_coco.config.deployer import TOKEN_PROXY_HOST, deploy_credentials
from inspect_coco.config.oauth import OAuthTokens, save_cached_tokens


@pytest.fixture
def oauth_sf_home(tmp_path, monkeypatch):
    """Set up an OAuth connection config with cached tokens."""
    monkeypatch.setenv("SNOWFLAKE_HOME", str(tmp_path))
    monkeypatch.delenv("INSPECT_COCO_SNOWFLAKE_CONNECTION", raising=False)

    # Cache valid tokens (uses file fallback since keyring is disabled in tests)
    save_cached_tokens(
        OAuthTokens(
            access_token="cached-at",
            refresh_token="cached-rt",
            expires_at=time.time() + 600,
            account="testorg-testaccount",
            role="ANALYST",
        )
    )

    (tmp_path / "connections.toml").write_text("""
[default]
account = "testorg-testaccount"
user = "testuser"
authenticator = "OAUTH_AUTHORIZATION_CODE"
role = "ANALYST"
""")
    return tmp_path


class TestOAuthResolution:
    def test_resolves_oauth_connection(self, oauth_sf_home):
        config = resolve_connection()
        assert config.authenticator == "OAUTH_AUTHORIZATION_CODE"
        assert config.oauth_access_token == "cached-at"
        assert config.account == "testorg-testaccount"

    @pytest.mark.asyncio
    async def test_deployer_sets_oauth_host(self, oauth_sf_home):
        config = resolve_connection()
        exec_fn = AsyncMock()
        exec_fn.return_value.returncode = 0
        exec_fn.return_value.stdout = ""
        exec_fn.return_value.stderr = ""

        env = await deploy_credentials(config, exec_fn)

        assert env["SNOWFLAKE_OAUTH_TOKEN_HOST"] == TOKEN_PROXY_HOST
        assert "SNOWFLAKE_TOKEN" not in env
        assert "SNOWFLAKE_PRIVATE_KEY_FILE" not in env

    @pytest.mark.asyncio
    async def test_deployer_writes_oauth_connections_toml(self, oauth_sf_home):
        config = resolve_connection()
        exec_fn = AsyncMock()
        exec_fn.return_value.returncode = 0
        exec_fn.return_value.stdout = ""
        exec_fn.return_value.stderr = ""

        await deploy_credentials(config, exec_fn)

        # Find the connections.toml write call
        toml_calls = [c for c in exec_fn.call_args_list if "connections.toml" in str(c)]
        assert len(toml_calls) >= 1
        toml_content = str(toml_calls[0])
        assert 'authenticator = "OAUTH"' in toml_content
        assert "cached-at" in toml_content


@pytest.mark.live
class TestOAuthLive:
    """Live tests require real Snowflake OAuth tokens. Skipped by default."""

    def test_live_oauth_connection(self):
        config = resolve_connection()
        assert config.authenticator == "OAUTH_AUTHORIZATION_CODE"
