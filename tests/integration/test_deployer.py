"""Docker integration tests for credential deployment."""

from __future__ import annotations

from pathlib import Path

import pytest

from inspect_coco.config.connection import SnowflakeConnectionConfig
from inspect_coco.config.deployer import deploy_credentials

pytestmark = pytest.mark.docker

DUMMY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7o4qne60TB3pY
6rknWBMcKaMYR2RKhGa7RkwGI0R3ZBMZPCkijRiNbJOxBpn0LfEZSKIMQnLPeChi
kgZL4A+eUsYZMJjQEMeMSGafK4cTZ0aJQQRVQ8wlRJlONwB8dFJvSDHvGJPOZmOk
jJWDqCzBVIqWJyIjS+K0qBJfz5RjLKw5jM+hL9nHtLfG5H9ealqlnSr7JKtUfVW
-----END PRIVATE KEY-----
"""


@pytest.fixture
def jwt_config(tmp_path: Path) -> SnowflakeConnectionConfig:
    """Create a JWT config with a real PEM file."""
    key_file = tmp_path / "test_key.p8"
    key_file.write_text(DUMMY_PEM)
    return SnowflakeConnectionConfig(
        account="testorg-testaccount",
        user="testuser",
        host="testorg-testaccount.snowflakecomputing.com",
        role="SYSADMIN",
        warehouse="COMPUTE_WH",
        private_key_path=str(key_file),
    )


@pytest.fixture
def pat_config() -> SnowflakeConnectionConfig:
    """Create a PAT config."""
    return SnowflakeConnectionConfig(
        account="patorg-pataccount",
        user="patuser",
        host="patorg-pataccount.snowflakecomputing.com",
        role="ANALYST",
        token="test-pat-token-123",
    )


class TestDeployJWT:
    @pytest.mark.asyncio
    async def test_key_file_deployed(self, container, jwt_config):
        env_vars = await deploy_credentials(jwt_config, container)

        # Verify key file exists
        result = await container(cmd=["ls", "-la", env_vars["SNOWFLAKE_PRIVATE_KEY_FILE"]])
        assert result.success, f"Key file not found: {result.stderr}"

    @pytest.mark.asyncio
    async def test_key_file_permissions(self, container, jwt_config):
        env_vars = await deploy_credentials(jwt_config, container)

        # Check file permissions are 0600
        result = await container(cmd=["stat", "-c", "%a", env_vars["SNOWFLAKE_PRIVATE_KEY_FILE"]])
        assert result.stdout.strip() == "600", f"Expected 600, got {result.stdout.strip()}"

    @pytest.mark.asyncio
    async def test_key_file_content(self, container, jwt_config):
        env_vars = await deploy_credentials(jwt_config, container)

        result = await container(cmd=["cat", env_vars["SNOWFLAKE_PRIVATE_KEY_FILE"]])
        assert "-----BEGIN PRIVATE KEY-----" in result.stdout
        assert "-----END PRIVATE KEY-----" in result.stdout

    @pytest.mark.asyncio
    async def test_config_toml_jwt(self, container, jwt_config):
        await deploy_credentials(jwt_config, container)

        result = await container(cmd=["cat", "/root/.snowflake/connections.toml"])
        assert result.success
        assert 'authenticator = "SNOWFLAKE_JWT"' in result.stdout
        assert "private_key_file" in result.stdout
        assert 'account = "testorg-testaccount"' in result.stdout
        assert 'user = "testuser"' in result.stdout

    @pytest.mark.asyncio
    async def test_connections_toml_permissions(self, container, jwt_config):
        await deploy_credentials(jwt_config, container)

        result = await container(cmd=["stat", "-c", "%a", "/root/.snowflake/connections.toml"])
        assert result.stdout.strip() == "600"

    @pytest.mark.asyncio
    async def test_settings_json(self, container, jwt_config):
        await deploy_credentials(jwt_config, container)

        result = await container(cmd=["cat", "/root/.snowflake/cortex/settings.json"])
        assert result.success
        assert '"cortexAgentConnectionName": "default"' in result.stdout
        assert '"autoUpdate": false' in result.stdout

    @pytest.mark.asyncio
    async def test_env_vars_returned(self, container, jwt_config):
        env_vars = await deploy_credentials(jwt_config, container)

        assert env_vars["SNOWFLAKE_ACCOUNT"] == "testorg-testaccount"
        assert env_vars["SNOWFLAKE_USER"] == "testuser"
        assert env_vars["SNOWFLAKE_ROLE"] == "SYSADMIN"
        assert env_vars["SNOWFLAKE_WAREHOUSE"] == "COMPUTE_WH"
        assert "SNOWFLAKE_PRIVATE_KEY_FILE" in env_vars
        assert env_vars["SNOWFLAKE_CONNECTION_NAME"] == "default"


class TestDeployPAT:
    @pytest.mark.asyncio
    async def test_config_toml_pat(self, container, pat_config):
        await deploy_credentials(pat_config, container)

        result = await container(cmd=["cat", "/root/.snowflake/connections.toml"])
        assert result.success
        assert 'authenticator = "PROGRAMMATIC_ACCESS_TOKEN"' in result.stdout
        assert 'token = "test-pat-token-123"' in result.stdout
        assert 'account = "patorg-pataccount"' in result.stdout

    @pytest.mark.asyncio
    async def test_no_key_file_for_pat(self, container, pat_config):
        env_vars = await deploy_credentials(pat_config, container)

        assert "SNOWFLAKE_PRIVATE_KEY_FILE" not in env_vars
        assert env_vars["SNOWFLAKE_TOKEN"] == "test-pat-token-123"

    @pytest.mark.asyncio
    async def test_env_vars_pat(self, container, pat_config):
        env_vars = await deploy_credentials(pat_config, container)

        assert env_vars["SNOWFLAKE_ACCOUNT"] == "patorg-pataccount"
        assert env_vars["SNOWFLAKE_USER"] == "patuser"
        assert env_vars["SNOWFLAKE_ROLE"] == "ANALYST"


class TestDeployIdempotent:
    @pytest.mark.asyncio
    async def test_deploy_twice_succeeds(self, container, jwt_config):
        """Deploying credentials twice should not fail."""
        await deploy_credentials(jwt_config, container)
        env_vars = await deploy_credentials(jwt_config, container)
        assert env_vars["SNOWFLAKE_ACCOUNT"] == "testorg-testaccount"
