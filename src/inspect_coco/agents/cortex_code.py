"""Cortex Code agent for Inspect AI — runs cortex CLI in Docker sandbox."""

from __future__ import annotations

import logging

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ChatMessageAssistant, ModelOutput
from inspect_ai.util import sandbox

from inspect_coco.config.connection import resolve_connection
from inspect_coco.trajectory.parser import parse_stream_json

logger = logging.getLogger(__name__)


@agent
def cortex_code(
    timeout_sec: int = 900,
    skills: list[str] | None = None,
    remove_skills: list[str] | None = None,
    model_name: str | None = None,
    connection_name: str | None = None,
) -> Agent:
    """Cortex Code agent — runs the cortex CLI in a Docker sandbox.

    Args:
        timeout_sec: Maximum execution time for the cortex CLI.
        skills: Custom skill paths to load.
        remove_skills: Bundled skills to disable.
        model_name: Model to use (e.g. "claude-sonnet-4-5").
        connection_name: Named Snowflake connection to use.
    """
    _credentials_deployed = False

    async def execute(state: AgentState) -> AgentState:
        nonlocal _credentials_deployed

        # Deploy credentials on first invocation
        if not _credentials_deployed:
            config = resolve_connection(connection_name)
            env_vars = await _deploy_to_sandbox(config)
            _credentials_deployed = True
        else:
            config = resolve_connection(connection_name)
            env_vars = _build_env_from_config(config)

        # Extract prompt from the last user message
        prompt = _extract_prompt(state)

        # Build cortex CLI command
        cmd = _build_command(prompt, model_name, skills)

        # Build environment
        env = {
            **env_vars,
            "COCO_TELEMETRY_DISABLED": "true",
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


async def _deploy_to_sandbox(config):
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

    return await _deploy(config, _exec_wrapper)


def _build_env_from_config(config) -> dict[str, str]:
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
    prompt: str,
    model_name: str | None,
    skills: list[str] | None,
) -> list[str]:
    """Build the cortex CLI command."""
    cmd = [
        "cortex",
        "--print",
        prompt,
        "--dangerously-allow-all-tool-calls",
        "--output-format",
        "stream-json",
    ]

    if model_name:
        cmd.extend(["--model", model_name])

    if skills:
        for skill_path in skills:
            cmd.extend(["--skill", skill_path])

    return cmd
