"""Tests for JWT authentication path.

Default (mocked): validates wiring without real credentials.
Live (opt-in): validates actual Snowflake JWT auth.

Run mocked:  pytest examples/auth/jwt/
Run live:    pytest examples/auth/jwt/ -m live
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from inspect_coco.config.connection import resolve_connection
from inspect_coco.config.deployer import deploy_credentials


@pytest.fixture
def jwt_sf_home(tmp_path, monkeypatch):
    """Set up a JWT connection config."""
    monkeypatch.setenv("SNOWFLAKE_HOME", str(tmp_path))
    monkeypatch.delenv("INSPECT_COCO_SNOWFLAKE_CONNECTION", raising=False)

    # Create a dummy key file
    key_file = tmp_path / "rsa_key.p8"
    key_file.write_text(
        "-----BEGIN PRIVATE KEY-----\nMIIBVAIBADANBg==\n-----END PRIVATE KEY-----\n"
    )

    (tmp_path / "connections.toml").write_text(f"""
[default]
account = "testorg-testaccount"
user = "testuser"
authenticator = "SNOWFLAKE_JWT"
private_key_path = "{key_file}"
role = "SYSADMIN"
""")
    return tmp_path


class TestJwtResolution:
    def test_resolves_jwt_connection(self, jwt_sf_home):
        config = resolve_connection()
        assert config.authenticator == "SNOWFLAKE_JWT"
        assert config.private_key_path is not None
        assert config.account == "testorg-testaccount"

    @pytest.mark.asyncio
    async def test_deployer_writes_key_to_sandbox(self, jwt_sf_home):
        config = resolve_connection()
        exec_fn = AsyncMock()
        exec_fn.return_value.returncode = 0
        exec_fn.return_value.stdout = ""
        exec_fn.return_value.stderr = ""

        env = await deploy_credentials(config, exec_fn)

        assert "SNOWFLAKE_PRIVATE_KEY_FILE" in env
        assert env["SNOWFLAKE_ACCOUNT"] == "testorg-testaccount"
        # Verify mkdir, base64 key write, connections.toml write, settings.json write
        assert exec_fn.call_count >= 4


@pytest.mark.live
class TestJwtLive:
    """Live tests require real Snowflake credentials. Skipped by default."""

    def test_live_jwt_connection(self):
        config = resolve_connection()
        assert config.authenticator == "SNOWFLAKE_JWT"
