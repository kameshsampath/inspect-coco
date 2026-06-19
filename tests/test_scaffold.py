"""Tests for scaffold module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inspect_coco.scaffold import (
    SkillInfo,
    detect_plugin,
    extract_instruction_from_skill,
    filter_skills,
    generate_suite,
)


@pytest.fixture
def plugin_project(tmp_path: Path) -> Path:
    """Create a mock CoCo plugin project."""
    # .cortex-plugin/plugin.json
    plugin_dir = tmp_path / ".cortex-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "test-plugin",
                "skills": [
                    {"name": "leaf-skill", "path": "skills/leaf-skill/SKILL.md"},
                    {"name": "router-skill", "path": "skills/router-skill/SKILL.md"},
                    {"name": "ignored-skill", "path": "skills/ignored-skill/SKILL.md"},
                ],
            }
        )
    )

    # Leaf skill
    leaf_dir = tmp_path / "skills" / "leaf-skill"
    leaf_dir.mkdir(parents=True)
    (leaf_dir / "SKILL.md").write_text(
        """\
---
name: leaf-skill
description: >
  A leaf skill that does useful work.
  Use when: "do useful work", "run leaf", "execute leaf".
---

## When to Load

Load when the user wants to:
- Perform a specific useful operation
- Generate output from input data

## Steps

### Step 1: Do the thing

Do the actual work here.
"""
    )

    # Router skill (has routing table)
    router_dir = tmp_path / "skills" / "router-skill"
    router_dir.mkdir(parents=True)
    (router_dir / "SKILL.md").write_text(
        """\
---
name: router-skill
description: Routes to sub-skills based on intent.
---

## Routing Table

| Intent | Load |
|--------|------|
| foo | sub-skill-a |
| bar | sub-skill-b |
"""
    )

    # Ignored skill (will be in .inspectignore)
    ignored_dir = tmp_path / "skills" / "ignored-skill"
    ignored_dir.mkdir(parents=True)
    (ignored_dir / "SKILL.md").write_text(
        """\
---
name: ignored-skill
description: This skill is experimental.
---

## When to Load

Load when testing experimental features.
"""
    )

    # .inspectignore
    (tmp_path / ".inspectignore").write_text("skills/ignored-skill/\n")

    return tmp_path


class TestDetectPlugin:
    def test_detects_from_plugin_json(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        assert len(skills) == 3
        names = [s.name for s in skills]
        assert "leaf-skill" in names
        assert "router-skill" in names

    def test_explicit_plugin_dir(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project, plugin_dir=plugin_project / "skills" / "leaf-skill")
        assert len(skills) == 1
        assert skills[0].name == "leaf-skill"

    def test_parses_description(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        leaf = next(s for s in skills if s.name == "leaf-skill")
        assert "useful work" in leaf.description

    def test_parses_when_to_load(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        leaf = next(s for s in skills if s.name == "leaf-skill")
        assert len(leaf.when_to_load) == 2
        assert "Perform a specific useful operation" in leaf.when_to_load[0]

    def test_detects_router(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        router = next(s for s in skills if s.name == "router-skill")
        assert router.is_router is True

    def test_no_plugin_json(self, tmp_path: Path) -> None:
        skills = detect_plugin(tmp_path)
        assert skills == []

    def test_fallback_skills_dir(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: my-skill\ndescription: test\n---\n")
        skills = detect_plugin(tmp_path)
        assert len(skills) == 1


class TestFilterSkills:
    def test_removes_routers(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        filtered = filter_skills(skills, plugin_project)
        names = [s.name for s in filtered]
        assert "router-skill" not in names

    def test_applies_inspectignore(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        filtered = filter_skills(skills, plugin_project)
        names = [s.name for s in filtered]
        assert "ignored-skill" not in names

    def test_leaf_passes_through(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        filtered = filter_skills(skills, plugin_project)
        names = [s.name for s in filtered]
        assert "leaf-skill" in names

    def test_only_skills_filter(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        filtered = filter_skills(skills, plugin_project, only_skills=["leaf-skill"])
        assert len(filtered) == 1
        assert filtered[0].name == "leaf-skill"

    def test_extra_ignores(self, plugin_project: Path) -> None:
        skills = detect_plugin(plugin_project)
        filtered = filter_skills(skills, plugin_project, extra_ignores=["skills/leaf-skill/"])
        names = [s.name for s in filtered]
        assert "leaf-skill" not in names


class TestGenerateSuite:
    def test_creates_files(self, tmp_path: Path) -> None:
        skill = SkillInfo(
            name="test-skill",
            path=tmp_path / "SKILL.md",
            description="A test skill",
            when_to_load=["- Do something useful"],
        )
        output_dir = tmp_path / "evals"
        files = generate_suite(skill, output_dir)

        assert len(files) == 5
        assert (output_dir / "test-skill" / "suite.yaml").exists()
        assert (output_dir / "test-skill" / "basic-prompt" / "task.py").exists()
        assert (output_dir / "test-skill" / "basic-prompt" / "task.toml").exists()
        assert (output_dir / "test-skill" / "basic-prompt" / "instruction.md").exists()
        assert (output_dir / "test-skill" / "basic-prompt" / "tests" / "test.sh").exists()

    def test_dry_run_no_writes(self, tmp_path: Path) -> None:
        skill = SkillInfo(
            name="test-skill",
            path=tmp_path / "SKILL.md",
            description="A test skill",
        )
        output_dir = tmp_path / "evals"
        files = generate_suite(skill, output_dir, dry_run=True)

        assert len(files) == 5
        assert not output_dir.exists()

    def test_suite_yaml_content(self, tmp_path: Path) -> None:
        skill = SkillInfo(name="my-skill", path=tmp_path / "SKILL.md", description="desc")
        output_dir = tmp_path / "evals"
        generate_suite(skill, output_dir)

        content = (output_dir / "my-skill" / "suite.yaml").read_text()
        assert "name: my-skill-evals" in content
        assert "skill: my-skill" in content
        assert "tasks: auto" in content

    def test_task_toml_content(self, tmp_path: Path) -> None:
        skill = SkillInfo(name="my-skill", path=tmp_path / "SKILL.md", description="desc")
        output_dir = tmp_path / "evals"
        generate_suite(skill, output_dir)

        content = (output_dir / "my-skill" / "basic-prompt" / "task.toml").read_text()
        assert "my-skill-basic-prompt" in content
        assert "epochs = 3" in content

    def test_test_sh_executable(self, tmp_path: Path) -> None:
        skill = SkillInfo(name="my-skill", path=tmp_path / "SKILL.md", description="desc")
        output_dir = tmp_path / "evals"
        generate_suite(skill, output_dir)

        test_sh = output_dir / "my-skill" / "basic-prompt" / "tests" / "test.sh"
        assert test_sh.stat().st_mode & 0o111  # executable bit set


class TestExtractInstruction:
    def test_has_idd_sections(self) -> None:
        skill = SkillInfo(
            name="my-skill",
            path=Path("/fake"),
            description="Create reports from data",
            when_to_load=["- Generate PDF reports", "- Export data to CSV"],
        )
        result = extract_instruction_from_skill(skill)

        assert "## Goal" in result
        assert "## Requirements" in result
        assert "## Constraints" in result
        assert "## Output" in result

    def test_goal_from_description(self) -> None:
        skill = SkillInfo(
            name="my-skill",
            path=Path("/fake"),
            description="Create reports from data",
        )
        result = extract_instruction_from_skill(skill)
        assert "Create reports from data" in result

    def test_requirements_from_when_to_load(self) -> None:
        skill = SkillInfo(
            name="my-skill",
            path=Path("/fake"),
            description="desc",
            when_to_load=["- Generate PDF reports", "- Export data to CSV"],
        )
        result = extract_instruction_from_skill(skill)
        assert "generate pdf reports" in result.lower()
        assert "export data to csv" in result.lower()

    def test_default_constraints(self) -> None:
        skill = SkillInfo(name="x", path=Path("/fake"), description="d")
        result = extract_instruction_from_skill(skill)
        assert "Do not modify files outside /workspace" in result

    def test_output_has_todo(self) -> None:
        skill = SkillInfo(name="x", path=Path("/fake"), description="d")
        result = extract_instruction_from_skill(skill)
        assert "TODO" in result
