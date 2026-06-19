"""Trajectory parsing for cortex exec --format json output.

Parses the NDJSON (newline-delimited JSON) output from `cortex exec --format json`
into structured data for Inspect AI integration.

Event types:
- system (subtype: init) — session metadata, tools, skills, model
- assistant — model responses: text, tool_use, thinking blocks
- user — tool results (synthetic messages)
- result — final outcome with duration, usage, and error status
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A tool invocation captured from the trajectory."""

    name: str
    tool_use_id: str
    input: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    """A tool result captured from the trajectory."""

    tool_use_id: str
    content: str = ""


@dataclass
class Usage:
    """Token usage from the cortex exec run."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class Trajectory:
    """Parsed trajectory from cortex exec --format json output."""

    session_id: str = ""
    model: str = ""
    final_response: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    skills_loaded: list[str] = field(default_factory=list)
    tools_available: list[str] = field(default_factory=list)
    duration_ms: int = 0
    num_turns: int = 0
    usage: Usage = field(default_factory=Usage)
    is_error: bool = False
    error_messages: list[str] = field(default_factory=list)
    raw_events: list[dict] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.usage.input_tokens + self.usage.output_tokens


def parse_stream_json(output: str, exit_code: int = 0) -> Trajectory:
    """Parse cortex exec --format json output (NDJSON).

    Args:
        output: Raw stdout from cortex exec.
        exit_code: Process exit code (0 = success).

    Returns:
        Parsed Trajectory with extracted data.
    """
    trajectory = Trajectory()
    last_assistant_text = ""

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        # Skip non-JSON lines (e.g., update notices)
        if not line.startswith("{"):
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        trajectory.raw_events.append(event)
        event_type = event.get("type", "")

        if event_type == "system" and event.get("subtype") == "init":
            _handle_init(trajectory, event)

        elif event_type == "assistant":
            last_assistant_text = _handle_assistant(trajectory, event, last_assistant_text)

        elif event_type == "user":
            _handle_user(trajectory, event)

        elif event_type == "result":
            _handle_result(trajectory, event, last_assistant_text)

    # If result event didn't set final_response, use last assistant text
    if not trajectory.final_response and last_assistant_text:
        trajectory.final_response = last_assistant_text

    # Mark error if exit code non-zero and not already marked
    if exit_code != 0 and not trajectory.is_error:
        trajectory.is_error = True

    return trajectory


def _handle_init(trajectory: Trajectory, event: dict) -> None:
    """Process system init event."""
    trajectory.session_id = event.get("session_id", "")
    trajectory.model = event.get("model", "")
    trajectory.tools_available = event.get("tools", [])
    trajectory.skills_loaded = event.get("skills", [])


def _handle_assistant(trajectory: Trajectory, event: dict, last_text: str) -> str:
    """Process assistant message event. Returns updated last_text."""
    message = event.get("message", {})
    content_blocks = message.get("content", [])

    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type", "")

        if block_type == "text":
            last_text = block.get("text", "")

        elif block_type == "tool_use":
            trajectory.tool_calls.append(
                ToolCall(
                    name=block.get("name", ""),
                    tool_use_id=block.get("id", ""),
                    input=block.get("input", {}),
                )
            )

    return last_text


def _handle_user(trajectory: Trajectory, event: dict) -> None:
    """Process user message event (tool results)."""
    message = event.get("message", {})
    content_blocks = message.get("content", [])

    for block in content_blocks:
        if not isinstance(block, dict):
            continue

        if block.get("type") == "tool_result":
            content = block.get("content", "")
            if isinstance(content, list):
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            trajectory.tool_results.append(
                ToolResult(
                    tool_use_id=block.get("tool_use_id", ""),
                    content=str(content)[:1000],  # truncate large results
                )
            )


def _handle_result(trajectory: Trajectory, event: dict, last_text: str) -> None:
    """Process result event (final outcome)."""
    trajectory.final_response = event.get("result", last_text)
    trajectory.is_error = event.get("is_error", False)
    trajectory.duration_ms = event.get("duration_ms", 0)
    trajectory.num_turns = event.get("num_turns", 0)

    if event.get("errors"):
        trajectory.error_messages = event["errors"]

    usage_data = event.get("usage", {})
    trajectory.usage = Usage(
        input_tokens=usage_data.get("input_tokens", 0),
        output_tokens=usage_data.get("output_tokens", 0),
        cache_creation_input_tokens=usage_data.get("cache_creation_input_tokens", 0),
        cache_read_input_tokens=usage_data.get("cache_read_input_tokens", 0),
    )
