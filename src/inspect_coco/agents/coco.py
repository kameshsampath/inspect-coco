"""Cortex Code agent for Inspect AI — runs cortex CLI in Docker sandbox."""

from __future__ import annotations

import logging
import os

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ChatMessageAssistant, ModelOutput
from inspect_ai.util import sandbox

from inspect_coco.config.connection import resolve_connection
from inspect_coco.trajectory.parser import parse_stream_json

logger = logging.getLogger(__name__)


@agent
def coco(
    timeout_sec: int = 900,
    max_turns: int | None = None,
    remove_skills: list[str] | None = None,
    model_name: str | None = None,
    connection_name: str | None = None,
    workdir: str | None = None,
) -> Agent:
    """CoCo agent — runs `cortex exec` in a Docker sandbox.

    Uses the CI/CD-optimized `cortex exec` command (beta) which runs
    non-interactively with plan mode disabled and interactive prompts
    auto-rejected. Model defaults to CoCo auto mode unless overridden.

    Args:
        timeout_sec: Maximum execution time for the cortex CLI.
        max_turns: Maximum agentic turns (safety ceiling).
        remove_skills: Bundled skills to disable.
        model_name: Model override (e.g. "claude-sonnet-4-5"). Default: auto mode.
        connection_name: Named Snowflake connection to use.
        workdir: Working directory inside the sandbox.
    """
    _credentials_deployed = False
    _token_proxy = None

    async def execute(state: AgentState) -> AgentState:
        nonlocal _credentials_deployed, _token_proxy

        # Deploy credentials on first invocation
        if not _credentials_deployed:
            config = resolve_connection(connection_name)

            # Start token proxy for OAuth connections
            if config.oauth_access_token:
                from inspect_coco.proxy.server import TokenProxy

                _token_proxy = TokenProxy(account=config.account, role=config.role)
                _token_proxy.start()

            env_vars = await _deploy_to_sandbox(config, token_proxy=_token_proxy)
            _credentials_deployed = True
        else:
            config = resolve_connection(connection_name)
            env_vars = _build_env_from_config(config, token_proxy=_token_proxy)

        # Resolve model: explicit param > env var > None (CLI default)
        resolved_model = model_name or os.environ.get("INSPECT_COCO_MODEL")

        # Extract prompt from the last user message
        prompt = _extract_prompt(state)

        # Write prompt to file in sandbox (avoids shell escaping issues with large markdown)
        prompt_path = "/tmp/inspect-coco-prompt.md"
        await sandbox().write_file(prompt_path, prompt)

        # Build cortex exec command (uses --file to read prompt)
        cmd = _build_command(
            prompt_file=prompt_path,
            model_name=resolved_model,
            max_turns=max_turns,
            connection_name=connection_name,
            workdir=workdir,
        )

        # Build environment
        cortex_channel = os.environ.get("INSPECT_COCO_CHANNEL", "stable")
        env = {
            **env_vars,
            "COCO_TELEMETRY_DISABLED": "true",
            "CORTEX_CHANNEL": cortex_channel,
        }
        if remove_skills:
            env["CORTEX_DISABLE_BUNDLED_SKILLS"] = ",".join(remove_skills)

        # Execute in sandbox
        logger.info("Running cortex CLI (timeout=%ds)", timeout_sec)
        result = await sandbox().exec(cmd=cmd, timeout=timeout_sec, env=env)

        # Parse trajectory from stream-json output
        trajectory = parse_stream_json(result.stdout, exit_code=result.returncode)

        if result.returncode != 0 and not trajectory.final_response:
            trajectory.final_response = (
                f"Agent exited with code {result.returncode}.\n"
                f"stderr: {result.stderr[:500] if result.stderr else 'none'}"
            )

        # Update agent state
        state.messages.append(ChatMessageAssistant(content=trajectory.final_response))
        state.output = ModelOutput.from_content(
            model="cortex-code",
            content=trajectory.final_response,
            stop_reason="stop" if result.returncode == 0 else "error",
        )

        return state

    return execute


async def _deploy_to_sandbox(config, token_proxy=None):
    """Deploy credentials into the sandbox and return env vars."""
    from inspect_coco.config.deployer import deploy_credentials as _deploy

    async def _exec_wrapper(cmd, timeout=None, env=None):
        result = await sandbox().exec(cmd=cmd, timeout=timeout or 30, env=env or {})
        from inspect_coco.config.deployer import ExecResult

        return ExecResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    env_vars = await _deploy(config, _exec_wrapper)
    if token_proxy:
        env_vars["TOKEN_PROXY_PORT"] = str(token_proxy.port)
    return env_vars


def _build_env_from_config(config, token_proxy=None) -> dict[str, str]:
    """Build env vars from config without redeploying."""
    env: dict[str, str] = {
        "SNOWFLAKE_ACCOUNT": config.account,
        "SNOWFLAKE_USER": config.user,
        "SNOWFLAKE_HOST": config.host,
        "SNOWFLAKE_CONNECTION_NAME": "default",
    }
    if config.role:
        env["SNOWFLAKE_ROLE"] = config.role
    if config.warehouse:
        env["SNOWFLAKE_WAREHOUSE"] = config.warehouse
    if token_proxy:
        env["TOKEN_PROXY_PORT"] = str(token_proxy.port)
    return env


def _extract_prompt(state: AgentState) -> str:
    """Extract the user prompt from agent state."""
    for msg in reversed(state.messages):
        if hasattr(msg, "role") and msg.role == "user":
            if isinstance(msg.content, str):
                return msg.content
            if isinstance(msg.content, list):
                texts = [c.text for c in msg.content if hasattr(c, "text")]
                return "\n".join(texts)
    return ""


def _build_command(
    prompt_file: str,
    model_name: str | None,
    max_turns: int | None = None,
    connection_name: str | None = None,
    workdir: str | None = None,
) -> list[str]:
    """Build the cortex exec command for CI/CD non-interactive execution."""
    cmd = [
        "cortex",
        "exec",
        "--file",
        prompt_file,
        "--format",
        "json",
        "--bypass",
        "--no-history",
    ]

    if model_name:
        cmd.extend(["--model", model_name])

    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])

    if connection_name:
        cmd.extend(["--connection", connection_name])

    if workdir:
        cmd.extend(["--workdir", workdir])

    return cmd
