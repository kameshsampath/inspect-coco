""".inspectignore pattern matching for scaffold generation."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

# Default patterns always excluded (even without .inspectignore)
DEFAULT_EXCLUDES = [
    ".git/",
    ".git/**",
    ".venv/",
    ".venv/**",
    "venv/",
    "venv/**",
    "node_modules/",
    "node_modules/**",
    "__pycache__/",
    "__pycache__/**",
    ".pytest_cache/",
    ".pytest_cache/**",
    ".ruff_cache/",
    ".ruff_cache/**",
    ".mypy_cache/",
    ".mypy_cache/**",
    "shared/",
    "shared/**",
    "references/",
    "references/**",
    "*.draft.md",
]


def load_inspectignore(project_root: Path) -> list[str]:
    """Load .inspectignore patterns from project root.

    Combines user patterns with default exclusions.
    Format: gitignore-style, one pattern per line, # for comments.

    Args:
        project_root: Directory containing .inspectignore file.

    Returns:
        List of glob patterns to exclude.
    """
    patterns = list(DEFAULT_EXCLUDES)

    ignore_file = project_root / ".inspectignore"
    if ignore_file.exists():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)

    return patterns


def is_ignored(path: str, patterns: list[str]) -> bool:
    """Check if a path matches any ignore pattern.

    Args:
        path: Relative path to check (e.g., "skills/scaffold/gitlab/SKILL.md").
        patterns: List of gitignore-style glob patterns.

    Returns:
        True if the path should be excluded.
    """
    for pattern in patterns:
        # Directory pattern (trailing /)
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if path.startswith(dir_pattern + "/") or path == dir_pattern:
                return True
            # Also match if any path segment matches
            if f"/{dir_pattern}/" in f"/{path}/":
                return True
        # Glob pattern
        elif fnmatch.fnmatch(path, pattern):
            return True
        # Also check basename for simple patterns
        elif "/" not in pattern and fnmatch.fnmatch(Path(path).name, pattern):
            return True

    return False


def is_router_skill(skill_path: Path) -> bool:
    """Detect if a SKILL.md is a router (has routing table).

    Router skills dispatch to sub-skills and don't produce testable output.
    They are auto-excluded from eval generation.

    Args:
        skill_path: Path to a SKILL.md file.

    Returns:
        True if the skill contains a routing table.
    """
    if not skill_path.exists():
        return False

    content = skill_path.read_text()

    # Check for routing table markers
    has_routing_table = bool(re.search(r"##\s*(Routing\s*Table|Routes?)", content, re.IGNORECASE))
    has_table_with_load = "| Load |" in content or "load |" in content.lower()

    return has_routing_table or has_table_with_load
