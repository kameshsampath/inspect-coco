"""Snowflake connection resolution from existing TOML configuration files."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (does not override existing env vars)
load_dotenv()


@dataclass(frozen=True)
class SnowflakeConnectionConfig:
    """Resolved Snowflake connection configuration."""

    account: str
    user: str
    host: str
    role: str | None = None
    warehouse: str | None = None
    database: str | None = None
    schema: str | None = None
    private_key_path: str | None = None
    token: str | None = None

    @property
    def authenticator(self) -> str:
        if self.private_key_path:
            return "snowflake_jwt"
        if self.token:
            return "programmatic_access_token"
        raise ValueError(
            "No supported auth method found. "
            "Provide private_key_path (JWT) or token (PAT) in your connection config."
        )


class ConnectionResolutionError(Exception):
    """Raised when a Snowflake connection cannot be resolved."""


def snowflake_home() -> Path:
    """Return the Snowflake config directory, honouring SNOWFLAKE_HOME."""
    home = os.environ.get("SNOWFLAKE_HOME", "")
    if home:
        return Path(home)
    return Path.home() / ".snowflake"


def resolve_connection(connection_name: str | None = None) -> SnowflakeConnectionConfig:
    """Resolve a Snowflake connection from existing TOML files.

    Resolution order for connection name:
        1. Explicit connection_name parameter
        2. SNOWFLAKE_CONNECTION_NAME environment variable
        3. default_connection_name field in TOML file
        4. Fallback to "default"

    File lookup order (using SNOWFLAKE_HOME or ~/.snowflake):
        1. connections.toml (newer format) — top-level [connection_name]
        2. config.toml (older format) — nested [connections.connection_name]
    """
    sf_home = snowflake_home()
    name = connection_name or os.environ.get("SNOWFLAKE_CONNECTION_NAME", "")

    # Try connections.toml first (newer format)
    connections_path = sf_home / "connections.toml"
    if connections_path.exists():
        data = _load_toml(connections_path)
        resolved_name = name or data.get("default_connection_name", "default")
        if resolved_name in data:
            return _parse_connection_section(data[resolved_name], resolved_name)

    # Fall back to config.toml (older format)
    config_path = sf_home / "config.toml"
    if config_path.exists():
        data = _load_toml(config_path)
        resolved_name = name or data.get("default_connection_name", "default")
        connections = data.get("connections", {})
        if resolved_name in connections:
            return _parse_connection_section(connections[resolved_name], resolved_name)

    raise ConnectionResolutionError(
        f"No Snowflake connection found. "
        f"Looked for connections in: {connections_path}, {config_path}. "
        f"Ensure a valid connection exists in your Snowflake config directory "
        f"({sf_home})."
    )


def _load_toml(path: Path) -> dict:
    """Load and parse a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def _parse_connection_section(section: dict, connection_name: str) -> SnowflakeConnectionConfig:
    """Parse a TOML connection section into SnowflakeConnectionConfig."""
    account = section.get("account", "")
    if not account:
        raise ConnectionResolutionError(
            f"Connection '{connection_name}' is missing required field 'account'."
        )

    user = section.get("user", "")
    if not user:
        raise ConnectionResolutionError(
            f"Connection '{connection_name}' is missing required field 'user'."
        )

    host = section.get("host", f"{account}.snowflakecomputing.com")

    # Auth resolution: private_key_path → token → PAT env var
    private_key_path = section.get("private_key_path") or section.get("private_key_file")
    token = section.get("token")

    # PAT fallback from environment
    if not private_key_path and not token:
        pat_env_key = f"PAT_{account.upper()}"
        token = os.environ.get(pat_env_key)

    # Reject password-only configs
    if not private_key_path and not token:
        if section.get("password"):
            raise ConnectionResolutionError(
                f"Connection '{connection_name}' uses password authentication, "
                f"which is not supported. Use key-pair (JWT) or PAT instead."
            )
        raise ConnectionResolutionError(
            f"Connection '{connection_name}' has no supported auth method. "
            f"Provide private_key_path (JWT) or token (PAT)."
        )

    return SnowflakeConnectionConfig(
        account=account,
        user=user,
        host=host,
        role=section.get("role"),
        warehouse=section.get("warehouse"),
        database=section.get("database"),
        schema=section.get("schema"),
        private_key_path=private_key_path,
        token=token,
    )
