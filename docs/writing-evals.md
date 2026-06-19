# Writing Eval Tasks

How to create eval tasks for your CoCo skills.

## Quick Way: Use the CoCo Skill

```
$inspect-coco:create-task
```

This walks you through creating a task with guided prompts.

## Manual Way

Create a directory with three files:

```
my-eval/
├── task.toml
├── instruction.md
└── tests/
    └── test.sh
```

### Step 1: Write instruction.md

Use the IDD template:

```markdown
## Goal

<What should exist after the agent runs>

## Requirements

- <Intent statement 1>
- <Intent statement 2>

## Constraints

- Do not modify files outside /workspace
- <Your constraints>

## Output

Success criteria:
- <Verifiable condition 1>
- <Verifiable condition 2>
```

> [!TIP]
> Run the IDD scorer on your instruction before committing:
> ```python
> from inspect_coco.idd import score_instruction, explain_score
> score = score_instruction(open("instruction.md").read())
> print(explain_score(score))
> ```

### Step 2: Write test.sh

The test script runs after the agent finishes. Exit code 0 = pass, non-zero = fail.

```bash
#!/bin/bash
set -e

# Check file exists
test -f /workspace/output.txt

# Check content
grep -q "expected string" /workspace/output.txt

echo "PASS"
```

Common patterns:

```bash
# File existence
test -f /workspace/app.py

# Python runs without error
python /workspace/app.py

# JSON is valid
python -c "import json; json.load(open('/workspace/data.json'))"

# Specific content
grep -q "class MyClass" /workspace/app.py

# pytest
cd /workspace && pytest tests/ -v
```

### Step 3: Write task.toml

Minimal:

```toml
version = "1.0"

[metadata]
name = "my-eval"

[agent]
timeout_sec = 900
```

See [task.toml reference](task-toml.md) for all options.

### Step 4: Run

```bash
inspect-coco run my-eval/
```

## Design Principles

### One eval, one behavior

Each eval tests exactly one thing. Don't combine "create a file AND fix a bug AND run tests" into one task. Split them:

```
evals/
├── create-config-file/     # tests: can agent create config?
├── fix-import-error/       # tests: can agent fix imports?
└── run-test-suite/         # tests: can agent run pytest?
```

Benefits:
- When something fails, you know exactly which behavior broke
- Tasks run in parallel (faster)
- Easy to add/remove individual tests

### Starter files

If the agent needs existing files to work with (code to fix, config to modify), put them in `starter/`:

```
fix-import-error/
├── task.toml
├── instruction.md
├── starter/
│   └── app.py          # broken file for agent to fix
└── tests/
    └── test.sh
```

Files in `starter/` are copied to `/workspace/` before the agent runs.

### Custom Docker environment

If your eval needs specific tools or services, add a `compose.yaml`:

```yaml
services:
  default:
    build:
      context: ../../src/inspect_coco/sandbox
      dockerfile: Dockerfile
    init: true
    command: ["tail", "-f", "/dev/null"]
    environment:
      - DATABASE_URL=postgres://localhost/test
```

> [!IMPORTANT]
> The service must be named `default`. Inspect requires this.

## Scaffolding from an Existing Plugin

If you have a CoCo plugin with skills, the scaffold skill auto-generates evals:

```
$inspect-coco:scaffold
```

It reads your `.cortex-plugin/plugin.json`, finds leaf skills (skips routers),
and creates one eval per skill.
See [scaffold skill](../skills/scaffold/SKILL.md) for details.
