"""Tests for .inspectignore pattern matching."""

from __future__ import annotations

from pathlib import Path

from inspect_coco.ignores import is_ignored, is_router_skill, load_inspectignore


class TestLoadInspectignore:
    def test_default_patterns_always_present(self, tmp_path: Path):
        patterns = load_inspectignore(tmp_path)
        assert ".git/" in patterns
        assert ".venv/" in patterns
        assert "node_modules/" in patterns
        assert "__pycache__/" in patterns
        assert "shared/" in patterns
        assert "references/" in patterns
        assert "*.draft.md" in patterns

    def test_loads_user_patterns(self, tmp_path: Path):
        (tmp_path / ".inspectignore").write_text("""\
# Skip gitlab scaffold
skills/scaffold/gitlab/

# WIP
my-wip-skill/
""")
        patterns = load_inspectignore(tmp_path)
        assert "skills/scaffold/gitlab/" in patterns
        assert "my-wip-skill/" in patterns

    def test_ignores_comments_and_blank_lines(self, tmp_path: Path):
        (tmp_path / ".inspectignore").write_text("""\
# This is a comment

skills/old/

# Another comment
""")
        from inspect_coco.ignores import DEFAULT_EXCLUDES

        patterns = load_inspectignore(tmp_path)
        user_patterns = [p for p in patterns if p not in DEFAULT_EXCLUDES]
        assert user_patterns == ["skills/old/"]


class TestIsIgnored:
    def test_directory_pattern(self):
        assert is_ignored("shared/utils.md", ["shared/"])
        assert is_ignored("skills/shared/helper.md", ["shared/"])

    def test_glob_pattern(self):
        assert is_ignored("my-skill.draft.md", ["*.draft.md"])
        assert not is_ignored("my-skill.md", ["*.draft.md"])

    def test_path_pattern(self):
        assert is_ignored("skills/scaffold/gitlab/SKILL.md", ["skills/scaffold/gitlab/"])
        assert not is_ignored("skills/scaffold/github/SKILL.md", ["skills/scaffold/gitlab/"])

    def test_references_excluded(self):
        assert is_ignored("references/auth-setup.md", ["references/"])
        assert is_ignored("skills/scaffold/references/idd.md", ["references/"])

    def test_non_matching_passes(self):
        assert not is_ignored("skills/idd/evaluate-prompt/SKILL.md", ["shared/", "*.draft.md"])

    def test_deep_glob(self):
        assert is_ignored("shared/deep/nested/file.md", ["shared/**"])


class TestIsRouterSkill:
    def test_router_detected(self, tmp_path: Path):
        skill = tmp_path / "SKILL.md"
        skill.write_text("""\
---
name: my-router
---

## Routing Table

| Intent | Triggers | Load |
|---|---|---|
| Sub A | "keyword" | `sub-a/SKILL.md` |
""")
        assert is_router_skill(skill)

    def test_leaf_not_router(self, tmp_path: Path):
        skill = tmp_path / "SKILL.md"
        skill.write_text("""\
---
name: my-leaf
---

## Steps

1. Do the thing
2. Check the result
""")
        assert not is_router_skill(skill)

    def test_nonexistent_file(self, tmp_path: Path):
        assert not is_router_skill(tmp_path / "missing.md")

    def test_routes_header_variant(self, tmp_path: Path):
        skill = tmp_path / "SKILL.md"
        skill.write_text("""\
---
name: router-v2
---

## Routes

| Intent | Load |
|---|---|
| A | `a/SKILL.md` |
""")
        assert is_router_skill(skill)
