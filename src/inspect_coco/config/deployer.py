"""Deploy Snowflake credentials into a Docker container."""

from __future__ import annotations

import json
from typing import Protocol

from inspect_coco.config.connection import SnowflakeConnectionConfig
from inspect_coco.config.pem import normalize_pem, pem_to_base64_payload, remote_key_path


class SandboxExec(Protocol):
    """Protocol for executing commands in a sandbox container."""

    async def __call__(
        self,
        cmd: list[str],
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult: ...


class ExecResult:
    """Minimal exec result for type compatibility."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def success(self) -> bool:
        return self.returncode == 0


async def deploy_credentials(
    config: SnowflakeConnectionConfig,
    exec_fn: SandboxExec,
    connection_name: str = "default",
) -> dict[str, str]:
    """Deploy Snowflake credentials into a Docker sandbox container.

    Performs:
        1. Creates ~/.snowflake/cortex directory structure
        2. Deploys private key (JWT) via base64 transport + chmod 0600
        3. Generates config.toml with correct authenticator
        4. Generates cortex settings.json
        5. Returns env vars dict for subsequent exec() calls

    Args:
        config: Resolved Snowflake connection configuration.
        exec_fn: Callable to execute commands in the sandbox.
        connection_name: Name for the connection entry in config.toml.

    Returns:
        Dict of environment variables to pass to subsequent exec() calls.
    """
    # 1. Create directory structure
    await exec_fn(cmd=["mkdir", "-p", "/root/.snowflake/cortex"])

    # 2. Deploy private key if JWT auth
    deployed_key_path: str | None = None
    if config.private_key_path:
        pem_content = normalize_pem(open(config.private_key_path).read())
        deployed_key_path = remote_key_path(connection_name, pem_content)
        payload = pem_to_base64_payload(config.private_key_path)

        await exec_fn(
            cmd=[
                "bash",
                "-c",
                f"echo '{payload}' | base64 -d > {deployed_key_path} && chmod 0600 {deployed_key_path}",
            ]
        )

    # 3. Generate connections.toml (newer format)
    connections_toml = _generate_connections_toml(config, connection_name, deployed_key_path)
    await exec_fn(
        cmd=[
            "bash",
            "-c",
            f"cat > /root/.snowflake/connections.toml << 'TOMLEOF'\n{connections_toml}\nTOMLEOF",
        ]
    )
    # Set required 0600 permissions (Snowflake CLI requirement)
    await exec_fn(cmd=["chmod", "0600", "/root/.snowflake/connections.toml"])

    # 4. Generate cortex settings.json
    settings = json.dumps(
        {"cortexAgentConnectionName": connection_name, "autoUpdate": False},
        indent=2,
    )
    await exec_fn(
        cmd=[
            "bash",
            "-c",
            f"cat > /root/.snowflake/cortex/settings.json << 'JSONEOF'\n{settings}\nJSONEOF",
        ]
    )

    # 5. Return env vars for exec calls
    return _build_env_vars(config, connection_name, deployed_key_path)


def _generate_connections_toml(
    config: SnowflakeConnectionConfig,
    connection_name: str,
    remote_key: str | None,
) -> str:
    """Generate connections.toml content for the container (newer format)."""
    lines = [
        f'default_connection_name = "{connection_name}"',
        "",
        f"[{connection_name}]",
        f'account = "{config.account}"',
        f'user = "{config.user}"',
        f'host = "{config.host}"',
    ]

    if remote_key:
        lines.append('authenticator = "SNOWFLAKE_JWT"')
        lines.append(f'private_key_file = "{remote_key}"')
    elif config.token:
        lines.append('authenticator = "PROGRAMMATIC_ACCESS_TOKEN"')
        lines.append(f'token = "{config.token}"')

    if config.role:
        lines.append(f'role = "{config.role}"')
    if config.warehouse:
        lines.append(f'warehouse = "{config.warehouse}"')
    if config.database:
        lines.append(f'database = "{config.database}"')
    if config.schema:
        lines.append(f'schema = "{config.schema}"')

    return "\n".join(lines)


def _build_env_vars(
    config: SnowflakeConnectionConfig,
    connection_name: str,
    remote_key: str | None,
) -> dict[str, str]:
    """Build environment variables dict for container exec calls."""
    env: dict[str, str] = {
        "SNOWFLAKE_ACCOUNT": config.account,
        "SNOWFLAKE_USER": config.user,
        "SNOWFLAKE_HOST": config.host,
        "SNOWFLAKE_CONNECTION_NAME": connection_name,
    }

    if remote_key:
        env["SNOWFLAKE_PRIVATE_KEY_FILE"] = remote_key
    if config.token:
        env["SNOWFLAKE_TOKEN"] = config.token
    if config.role:
        env["SNOWFLAKE_ROLE"] = config.role
    if config.warehouse:
        env["SNOWFLAKE_WAREHOUSE"] = config.warehouse
    if config.database:
        env["SNOWFLAKE_DATABASE"] = config.database
    if config.schema:
        env["SNOWFLAKE_SCHEMA"] = config.schema

    return env
