"""Tests for Snowflake TOML connection resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from inspect_coco.config.connection import (
    ConnectionResolutionError,
    SnowflakeConnectionConfig,
    resolve_connection,
)


@pytest.fixture
def sf_home(tmp_path, monkeypatch):
    """Set SNOWFLAKE_HOME to a temp directory."""
    monkeypatch.setenv("SNOWFLAKE_HOME", str(tmp_path))
    monkeypatch.delenv("SNOWFLAKE_CONNECTION_NAME", raising=False)
    return tmp_path


class TestResolveConnectionFromConnectionsToml:
    """Tests using the newer connections.toml format."""

    def test_jwt_connection(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
role = "SYSADMIN"
warehouse = "COMPUTE_WH"
private_key_path = "/path/to/key.p8"
""")
        config = resolve_connection()
        assert config.account == "myorg-myaccount"
        assert config.user == "testuser"
        assert config.host == "myorg-myaccount.snowflakecomputing.com"
        assert config.role == "SYSADMIN"
        assert config.warehouse == "COMPUTE_WH"
        assert config.private_key_path == "/path/to/key.p8"
        assert config.token is None
        assert config.authenticator == "SNOWFLAKE_JWT"

    def test_pat_connection(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
token = "pat-token-value"
""")
        config = resolve_connection()
        assert config.token == "pat-token-value"
        assert config.private_key_path is None
        assert config.authenticator == "PROGRAMMATIC_ACCESS_TOKEN"

    def test_named_connection(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[dev]
account = "devorg-devaccount"
user = "devuser"
private_key_path = "/dev/key.p8"

[prod]
account = "prodorg-prodaccount"
user = "produser"
private_key_path = "/prod/key.p8"
""")
        config = resolve_connection("prod")
        assert config.account == "prodorg-prodaccount"
        assert config.user == "produser"

    def test_connection_name_from_env(self, sf_home: Path, monkeypatch):
        monkeypatch.setenv("SNOWFLAKE_CONNECTION_NAME", "staging")
        (sf_home / "connections.toml").write_text("""
[staging]
account = "stg-account"
user = "stguser"
private_key_path = "/stg/key.p8"
""")
        config = resolve_connection()
        assert config.account == "stg-account"

    def test_default_connection_name_field(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
default_connection_name = "myconn"

[myconn]
account = "org-acct"
user = "u"
private_key_path = "/k.p8"
""")
        config = resolve_connection()
        assert config.account == "org-acct"

    def test_custom_host(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
host = "custom.snowflakecomputing.com"
private_key_path = "/key.p8"
""")
        config = resolve_connection()
        assert config.host == "custom.snowflakecomputing.com"

    def test_pat_fallback_from_env(self, sf_home: Path, monkeypatch):
        monkeypatch.setenv("PAT_MYORG-MYACCOUNT", "env-pat-value")
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
""")
        config = resolve_connection()
        assert config.token == "env-pat-value"
        assert config.authenticator == "PROGRAMMATIC_ACCESS_TOKEN"


class TestResolveConnectionFromConfigToml:
    """Tests using the older config.toml format."""

    def test_fallback_to_config_toml(self, sf_home: Path):
        (sf_home / "config.toml").write_text("""
default_connection_name = "default"

[connections.default]
account = "oldorg-oldaccount"
user = "olduser"
private_key_path = "/old/key.p8"
role = "ANALYST"
""")
        config = resolve_connection()
        assert config.account == "oldorg-oldaccount"
        assert config.role == "ANALYST"
        assert config.authenticator == "SNOWFLAKE_JWT"

    def test_config_toml_named_connection(self, sf_home: Path):
        (sf_home / "config.toml").write_text("""
[connections.analytics]
account = "analytics-acct"
user = "analyst"
token = "pat-123"
""")
        config = resolve_connection("analytics")
        assert config.account == "analytics-acct"
        assert config.token == "pat-123"


class TestResolveConnectionErrors:
    """Tests for error cases."""

    def test_no_toml_files(self, sf_home: Path):
        with pytest.raises(ConnectionResolutionError, match="No Snowflake connection found"):
            resolve_connection()

    def test_missing_account(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
user = "testuser"
private_key_path = "/key.p8"
""")
        with pytest.raises(ConnectionResolutionError, match="missing required field 'account'"):
            resolve_connection()

    def test_missing_user(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
private_key_path = "/key.p8"
""")
        with pytest.raises(ConnectionResolutionError, match="missing required field 'user'"):
            resolve_connection()

    def test_password_only_rejected(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
password = "secret123"
""")
        with pytest.raises(
            ConnectionResolutionError, match="password authentication.*not supported"
        ):
            resolve_connection()

    def test_no_auth_method(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
""")
        with pytest.raises(ConnectionResolutionError, match="no supported auth method"):
            resolve_connection()

    def test_connection_name_not_found(self, sf_home: Path):
        (sf_home / "connections.toml").write_text("""
[default]
account = "myorg-myaccount"
user = "testuser"
private_key_path = "/key.p8"
""")
        with pytest.raises(ConnectionResolutionError, match="No Snowflake connection found"):
            resolve_connection("nonexistent")


class TestSnowflakeConnectionConfig:
    """Tests for the config dataclass."""

    def test_authenticator_jwt(self):
        config = SnowflakeConnectionConfig(
            account="a", user="u", host="h", private_key_path="/k.p8"
        )
        assert config.authenticator == "SNOWFLAKE_JWT"

    def test_authenticator_pat(self):
        config = SnowflakeConnectionConfig(account="a", user="u", host="h", token="pat")
        assert config.authenticator == "PROGRAMMATIC_ACCESS_TOKEN"

    def test_authenticator_none_raises(self):
        config = SnowflakeConnectionConfig(account="a", user="u", host="h")
        with pytest.raises(ValueError, match="No supported auth method"):
            _ = config.authenticator
