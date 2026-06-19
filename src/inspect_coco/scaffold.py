"""Scaffold generator — auto-creates eval suites from CoCo plugin structure."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from inspect_coco.ignores import is_ignored, is_router_skill, load_inspectignore

logger = logging.getLogger(__name__)

TASK_TOML_TEMPLATE = """\
version = "1.0"

[metadata]
name = "{name}"
description = "{description}"
epochs = 3
idd_threshold = 0.6

[agent]
timeout_sec = 900
max_turns = 30

[environment]
test_timeout = 300
"""

TEST_SH_TEMPLATE = """\
#!/bin/bash
set -e

# TODO: Replace with actual verification for this eval scenario.
# Exit 0 = pass, non-zero = fail.

echo "PLACEHOLDER: Add verification logic for '{name}'"
exit 1
"""

SUITE_YAML_TEMPLATE = """\
name: {skill_name}-evals
description: Eval scenarios for {skill_name}
skill: {skill_name}

defaults:
  epochs: 3
  timeout_sec: 900
  idd_threshold: 0.6

tasks: auto
"""


@dataclass
class SkillInfo:
    """Discovered skill metadata."""

    name: str
    path: Path  # path to SKILL.md
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    when_to_load: list[str] = field(default_factory=list)
    is_router: bool = False


def detect_plugin(root: Path, plugin_dir: Path | None = None) -> list[SkillInfo]:
    """Detect skills from a CoCo plugin project.

    Looks for .cortex-plugin/plugin.json to find registered skills.
    Falls back to scanning plugin_dir for SKILL.md files.

    Args:
        root: Project root directory.
        plugin_dir: Explicit skills directory (overrides plugin.json).

    Returns:
        List of discovered SkillInfo objects.
    """
    skills: list[SkillInfo] = []

    if plugin_dir:
        # Direct scan of skills directory
        for skill_md in sorted(plugin_dir.rglob("SKILL.md")):
            info = _parse_skill_md(skill_md)
            if info:
                skills.append(info)
        return skills

    # Try .cortex-plugin/plugin.json
    plugin_json = root / ".cortex-plugin" / "plugin.json"
    if plugin_json.exists():
        data = json.loads(plugin_json.read_text())
        for entry in data.get("skills", []):
            skill_path = root / entry["path"]
            if skill_path.exists():
                info = _parse_skill_md(skill_path)
                if info:
                    info.name = entry.get("name", info.name)
                    skills.append(info)
        return skills

    # Fallback: scan for SKILL.md in skills/ directory
    skills_dir = root / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.rglob("SKILL.md")):
            info = _parse_skill_md(skill_md)
            if info:
                skills.append(info)

    return skills


def filter_skills(
    skills: list[SkillInfo],
    project_root: Path,
    extra_ignores: list[str] | None = None,
    only_skills: list[str] | None = None,
) -> list[SkillInfo]:
    """Filter skills: remove routers and ignored paths.

    Args:
        skills: All detected skills.
        project_root: Root for .inspectignore resolution.
        extra_ignores: Additional ignore patterns from CLI.
        only_skills: If set, only include these skill names.

    Returns:
        Filtered list of leaf skills.
    """
    patterns = load_inspectignore(project_root)
    if extra_ignores:
        patterns.extend(extra_ignores)

    result = []
    for skill in skills:
        # Filter by name if --skill specified
        if only_skills and skill.name not in only_skills:
            continue

        # Skip routers
        if skill.is_router:
            logger.debug("Skipping router skill: %s", skill.name)
            continue

        # Check ignore patterns against relative path
        rel_path = str(skill.path.relative_to(project_root))
        if is_ignored(rel_path, patterns):
            logger.debug("Skipping ignored skill: %s (%s)", skill.name, rel_path)
            continue

        result.append(skill)

    return result


def generate_suite(
    skill: SkillInfo,
    output_dir: Path,
    dry_run: bool = False,
) -> list[Path]:
    """Generate eval suite for a single skill.

    Creates:
        output_dir/<skill-name>/suite.yaml
        output_dir/<skill-name>/basic-prompt/task.toml
        output_dir/<skill-name>/basic-prompt/instruction.md
        output_dir/<skill-name>/basic-prompt/tests/test.sh

    Args:
        skill: Skill to generate eval for.
        output_dir: Root output directory for evals.
        dry_run: If True, report what would be created without writing.

    Returns:
        List of file paths that were (or would be) created.
    """
    suite_dir = output_dir / skill.name
    task_dir = suite_dir / "basic-prompt"
    tests_dir = task_dir / "tests"

    files: list[Path] = []

    # suite.yaml
    suite_yaml = suite_dir / "suite.yaml"
    suite_content = SUITE_YAML_TEMPLATE.format(skill_name=skill.name)
    files.append(suite_yaml)

    # task.toml
    task_toml = task_dir / "task.toml"
    description = f"Basic eval for {skill.name}: {skill.description[:80]}"
    task_toml_content = TASK_TOML_TEMPLATE.format(
        name=f"{skill.name}-basic-prompt",
        description=description,
    )
    files.append(task_toml)

    # instruction.md
    instruction_md = task_dir / "instruction.md"
    instruction_content = extract_instruction_from_skill(skill)
    files.append(instruction_md)

    # tests/test.sh
    test_sh = tests_dir / "test.sh"
    test_content = TEST_SH_TEMPLATE.format(name=skill.name)
    files.append(test_sh)

    if dry_run:
        return files

    # Write files
    for path, content in [
        (suite_yaml, suite_content),
        (task_toml, task_toml_content),
        (instruction_md, instruction_content),
        (test_sh, test_content),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if path.name == "test.sh":
            path.chmod(0o755)

    return files


def extract_instruction_from_skill(skill: SkillInfo) -> str:
    """Generate an IDD-structured instruction.md from skill metadata.

    Uses heuristics to populate each IDD section from SKILL.md content.
    The result is a starting point — user should refine specifics.

    Args:
        skill: Parsed skill info with description, triggers, when_to_load.

    Returns:
        Markdown string with IDD structure.
    """
    # Goal: first meaningful sentence from description
    goal = skill.description.strip()
    if not goal:
        goal = f"Invoke the {skill.name} skill and produce the expected output."

    # Requirements: from when_to_load bullets
    requirements = []
    for item in skill.when_to_load:
        # Convert "Load when the user wants to:" bullets into requirement statements
        cleaned = item.strip().lstrip("-").strip()
        if cleaned:
            requirements.append(f"- The agent must {cleaned.lower()}")

    if not requirements:
        requirements = [
            f"- The agent must successfully execute the {skill.name} skill",
            "- The output must match the expected structure",
        ]

    # Constraints: default safety set
    constraints = [
        "- Do not modify files outside /workspace",
        "- Do not install packages unless explicitly required by the task",
        "- Complete the task in a single pass without user interaction",
    ]

    # Output: placeholder requiring user input
    output = [
        "- TODO: Define verifiable success criteria",
        "- Example: File `/workspace/output.txt` exists with expected content",
        "- Example: Running `pytest /workspace/tests/` exits with code 0",
    ]

    sections = [
        "## Goal\n",
        goal,
        "\n\n## Requirements\n",
        "\n".join(requirements),
        "\n\n## Constraints\n",
        "\n".join(constraints),
        "\n\n## Output\n",
        "\n".join(output),
        "\n",
    ]

    return "".join(sections)


def _parse_skill_md(skill_path: Path) -> SkillInfo | None:
    """Parse a SKILL.md file to extract metadata.

    Reads YAML frontmatter and key sections.
    """
    if not skill_path.exists():
        return None

    content = skill_path.read_text()

    # Extract frontmatter
    name = skill_path.parent.name
    description = ""
    triggers: list[str] = []

    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)

        # Name
        name_match = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()

        # Description (may be multi-line with >)
        desc_match = re.search(r"^description:\s*>?\s*\n((?:[ \t]+.+\n?)+)", fm_text, re.MULTILINE)
        if desc_match:
            description = " ".join(desc_match.group(1).strip().splitlines())
            description = re.sub(r"\s+", " ", description).strip()
        else:
            # Single-line description
            desc_single = re.search(r"^description:\s*(?!>)(.+)$", fm_text, re.MULTILINE)
            if desc_single:
                description = desc_single.group(1).strip().strip('"').strip("'")

        # Triggers from "Use when:" in description
        trigger_match = re.search(r'Use when:\s*"([^"]+)"', description)
        if trigger_match:
            # Split by comma or "Use when:" patterns
            raw = re.findall(r'"([^"]+)"', description[description.find("Use when:") :])
            triggers = raw

    # Extract "When to Load" bullets (only the first bullet list after the header)
    when_to_load: list[str] = []
    wtl_match = re.search(r"##\s*When to Load\s*\n[^\n-]*\n((?:- .+\n?)+)", content)
    if wtl_match:
        for line in wtl_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                when_to_load.append(line)

    # Check if router
    is_router = is_router_skill(skill_path)

    return SkillInfo(
        name=name,
        path=skill_path,
        description=description,
        triggers=triggers,
        when_to_load=when_to_load,
        is_router=is_router,
    )
