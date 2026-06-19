"""Trajectory parsing for cortex CLI stream-json output.

Parses the --output-format stream-json output from cortex CLI into
structured data for Inspect AI integration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Trajectory:
    """Parsed trajectory from cortex stream-json output."""

    final_response: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    skill_invocations: list[str] = field(default_factory=list)
    raw_events: list[dict] = field(default_factory=list)
    exit_code: int = 0


def parse_stream_json(output: str, exit_code: int = 0) -> Trajectory:
    """Parse cortex --output-format stream-json output.

    Processes line-by-line JSON events, extracting tool calls,
    skill invocations, and the final assistant response.

    Args:
        output: Raw stdout from cortex CLI execution.
        exit_code: Process exit code (0 = success).

    Returns:
        Parsed Trajectory with extracted data.
    """
    trajectory = Trajectory(exit_code=exit_code)
    last_text = ""

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        trajectory.raw_events.append(event)

        # Extract based on event type
        event_type = event.get("type", "")

        if event_type == "assistant" or event_type == "text":
            text = event.get("text", "") or event.get("content", "")
            if text:
                last_text = text

        elif event_type == "tool_use" or event_type == "tool_call":
            trajectory.tool_calls.append(event)

        elif event_type == "skill":
            name = event.get("name", "")
            if name:
                trajectory.skill_invocations.append(name)

        # Also handle nested content arrays
        if "content" in event and isinstance(event["content"], list):
            for block in event["content"]:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        last_text = block.get("text", last_text)
                    elif block.get("type") in ("tool_use", "tool_call"):
                        trajectory.tool_calls.append(block)

    trajectory.final_response = last_text
    return trajectory
