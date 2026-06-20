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
    oauth_access_token: str | None = None

    @property
    def authenticator(self) -> str:
        if self.private_key_path:
            return "SNOWFLAKE_JWT"
        if self.token:
            return "PROGRAMMATIC_ACCESS_TOKEN"
        if self.oauth_access_token:
            return "OAUTH_AUTHORIZATION_CODE"
        raise ValueError(
            "No supported auth method found. "
            "Provide private_key_path (JWT), token (PAT), or run 'inspect-coco login'."
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
        2. INSPECT_COCO_SNOWFLAKE_CONNECTION environment variable
        3. default_connection_name field in TOML file
        4. Fallback to "default"

    File lookup order (using SNOWFLAKE_HOME or ~/.snowflake):
        1. connections.toml (newer format) — top-level [connection_name]
        2. config.toml (older format) — nested [connections.connection_name]
    """
    sf_home = snowflake_home()
    name = connection_name or os.environ.get("INSPECT_COCO_SNOWFLAKE_CONNECTION", "")

    # Try connections.toml first (newer format)
    connections_path = sf_home / "connections.toml"
    if connections_path.exists():
        data = _load_toml(connections_path)
        resolved_name = name or data.get("default_connection_name", "default")
        if resolved_name in data:
            return _parse_connection_section(data[resolved_name], resolved_name)
        # Connection not found - collect available names for error
        available = [
            k for k in data if k != "default_connection_name" and isinstance(data[k], dict)
        ]
        raise ConnectionResolutionError(
            f"Connection '{resolved_name}' not found in {connections_path}.\n"
            f"Available connections: {', '.join(available)}\n"
            f"Fix: set INSPECT_COCO_SNOWFLAKE_CONNECTION in your .env file to one of the above."
        )

    # Fall back to config.toml (older format)
    config_path = sf_home / "config.toml"
    if config_path.exists():
        data = _load_toml(config_path)
        resolved_name = name or data.get("default_connection_name", "default")
        connections = data.get("connections", {})
        if resolved_name in connections:
            return _parse_connection_section(connections[resolved_name], resolved_name)
        # Connection not found
        available = list(connections.keys())
        raise ConnectionResolutionError(
            f"Connection '{resolved_name}' not found in {config_path}.\n"
            f"Available connections: {', '.join(available)}\n"
            f"Fix: set INSPECT_COCO_SNOWFLAKE_CONNECTION in your .env file to one of the above."
        )

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

    # Check for unsupported authenticator types
    authenticator = section.get("authenticator", "").upper()
    unsupported_types = [
        "EXTERNALBROWSER",
        "OAUTH",
        "OAUTH_CLIENT_CREDENTIALS",
        "USERNAME_PASSWORD_MFA",
    ]
    if authenticator in unsupported_types:
        raise ConnectionResolutionError(
            f"Connection '{connection_name}' uses authenticator '{authenticator}', "
            f"which is not supported in Docker environments.\n"
            f"Supported methods: SNOWFLAKE_JWT (key-pair), PROGRAMMATIC_ACCESS_TOKEN (PAT), "
            f"or OAUTH_AUTHORIZATION_CODE (via 'inspect-coco login')."
        )

    # OAUTH_AUTHORIZATION_CODE: resolve via cached local OAuth tokens
    if authenticator == "OAUTH_AUTHORIZATION_CODE":
        oauth_access_token = _resolve_oauth_token(account, section.get("role"))
        return SnowflakeConnectionConfig(
            account=account,
            user=user,
            host=host,
            role=section.get("role"),
            warehouse=section.get("warehouse"),
            database=section.get("database"),
            schema=section.get("schema"),
            oauth_access_token=oauth_access_token,
        )

    # PAT fallback from environment
    if not private_key_path and not token:
        pat_env_key = f"PAT_{account.upper()}"
        token = os.environ.get(pat_env_key)

    # Also check token_file_path (PAT stored in a file)
    if not private_key_path and not token:
        token_file = section.get("token_file_path")
        if token_file:
            token_path = Path(token_file).expanduser()
            if token_path.exists():
                token = token_path.read_text().strip()

    # Reject password-only configs
    if not private_key_path and not token:
        if section.get("password"):
            raise ConnectionResolutionError(
                f"Connection '{connection_name}' uses password authentication, "
                f"which is not supported. Use key-pair (JWT) or PAT instead."
            )

        # Try OAuth cached tokens as last resort
        oauth_access_token = _try_oauth_token(account)
        if not oauth_access_token:
            raise ConnectionResolutionError(
                f"Connection '{connection_name}' has no supported auth method.\n"
                f"Supported: private_key_path/private_key_file (JWT), token/token_file_path (PAT), "
                f"or authenticator = 'OAUTH_AUTHORIZATION_CODE'.\n"
                f"See: https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections"
            )

        return SnowflakeConnectionConfig(
            account=account,
            user=user,
            host=host,
            role=section.get("role"),
            warehouse=section.get("warehouse"),
            database=section.get("database"),
            schema=section.get("schema"),
            oauth_access_token=oauth_access_token,
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


def _try_oauth_token(account: str) -> str | None:
    """Attempt to load a valid OAuth access token from cache (passive, no browser)."""
    from inspect_coco.config.oauth import get_valid_token, load_cached_tokens

    tokens = load_cached_tokens(account=account)
    if tokens is None:
        return None
    tokens = get_valid_token(tokens)
    return tokens.access_token


_oauth_token_cache: dict[str, str] = {}


def _resolve_oauth_token(account: str, role: str | None = None) -> str:
    """Get a valid OAuth access token, triggering the browser flow if needed."""
    from inspect_coco.config.oauth import authorize, get_valid_token, load_cached_tokens

    # In-memory cache to avoid repeated browser opens within the same process
    if account in _oauth_token_cache:
        tokens = load_cached_tokens(account=account)
        if tokens is not None and not tokens.is_expired:
            return tokens.access_token

    tokens = load_cached_tokens(account=account)
    if tokens is not None:
        tokens = get_valid_token(tokens)
        _oauth_token_cache[account] = tokens.access_token
        return tokens.access_token

    # No cached tokens — run the browser OAuth flow
    tokens = authorize(account=account, role=role)
    _oauth_token_cache[account] = tokens.access_token
    return tokens.access_token
