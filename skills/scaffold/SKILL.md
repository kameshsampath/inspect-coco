---
name: inspect-coco-scaffold
description: >
  Set up inspect-coco in a project and auto-generate eval tasks from existing
  CoCo skills/plugins. Reads plugin structure (SKILL.md files) and creates
  atomic eval tasks with IDD-structured instructions.
  Use when: "set up inspect-coco", "add inspect evals", "scaffold eval tasks",
  "create evaluation suite", "add coco eval", "generate evals from skills",
  "inspect-coco setup", "bootstrap eval tasks from plugin".
---

## When to Load

Load when the user wants to:
- Add inspect-coco to an existing project
- Auto-generate eval tasks from an existing CoCo skill/plugin
- Set up the evaluation framework for a new or existing plugin

## Stopping Points

Before generating eval tasks, ask the user:
1. Which plugin/skills directory to scan
2. Whether to use default .inspectignore patterns
3. Confirm the list of leaf skills that will get eval tasks

## Steps

### Step 1: Prerequisites Check

Verify the following are available:
- `uv` or `pip` (for dependency installation)
- Docker (required for sandbox execution)
- `~/.snowflake/connections.toml` exists with a valid connection (JWT or PAT)
- `cortex exec --help` works (beta channel required)

If any prerequisite is missing, explain what's needed and how to fix it.

### Step 2: Install inspect-coco

```bash
uv add git+https://github.com/kameshsampath/inspect-coco.git
```

### Step 3: Detect Plugin Structure

Read `.cortex-plugin/plugin.json` to discover registered skills. For each skill:
1. Read the SKILL.md file
2. Determine if it's a **router** (has routing table) or **leaf** (no routing table)
3. Only leaf skills get eval tasks (routers just dispatch)

Check for `.inspectignore` in the project root. Apply default exclusions:
- Router skills (auto-detected from routing table presence)
- `shared/` directories
- `references/` directories
- `*.draft.md` files

### Step 4: Generate Eval Tasks

For each non-ignored leaf skill, create an atomic eval task:

```
evals/<skill-name>/
├── task.toml          # Config: timeout, epochs, idd_threshold
├── instruction.md     # IDD-structured prompt derived from skill triggers
└── tests/
    └── test.sh        # Verification script
```

The `instruction.md` is generated using the IDD template:
- **Goal**: derived from the skill's description
- **Requirements**: derived from the skill's trigger phrases and expected behavior
- **Constraints**: default safety boundaries (no file modification outside /workspace)
- **Output**: verifiable success criteria

### Step 5: Generate .env

Create a `.env` file with sane defaults:
```
INSPECT_COCO_CHANNEL=beta
# INSPECT_COCO_MODEL=
SNOWFLAKE_CONNECTION_NAME=default
```

### Step 6: Verify

Run IDD scorer on all generated instructions:
```bash
uv run python -c "from inspect_coco.idd import score_instruction; ..."
```

Report: "Generated N eval tasks. IDD scores: min=X, avg=Y, max=Z"

## References

- [IDD Principles](references/idd-principles.md) — Goal/Requirements/Constraints/Output template
- [task.toml Spec](references/task-toml-spec.md) — Configuration format
- For deeper IDD help: `$devops-coco-agents:idd-evaluate-prompt` or `$devops-coco-agents:idd-rewrite-prompt`
