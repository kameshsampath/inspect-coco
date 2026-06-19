# Writing Evals

How to create eval tasks for your CoCo skills.

## Quick path: use the CoCo skill

```
$inspect-coco:create-task
```

This walks you through creating a task with guided prompts.

## Manual path

Create a directory with three files:

```
my-eval/
├── task.toml
├── instruction.md
└── tests/
    └── test.sh
```

### Step 1: Write instruction.md

Use the IDD template for consistent, deterministic results:

```markdown title="instruction.md"
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

!!! tip "Validate before committing"

    Run the IDD scorer on your instruction to catch quality issues early:

    ```bash
    inspect-coco idd-check my-eval/
    ```

### Step 2: Write tests/test.sh

The test script runs inside the Docker sandbox after the agent finishes. Exit code 0 means pass, non-zero means fail.

```bash title="tests/test.sh"
#!/bin/bash
set -e

# Check the file exists
test -f /workspace/output.txt

# Check the content
grep -q "expected string" /workspace/output.txt

echo "PASS"
```

??? example "Common test patterns"

    ```bash
    # File existence
    test -f /workspace/app.py

    # Python runs without error
    python /workspace/app.py

    # JSON is valid
    python -c "import json; json.load(open('/workspace/data.json'))"

    # Specific content present
    grep -q "class MyClass" /workspace/app.py

    # Run pytest
    cd /workspace && pytest tests/ -v
    ```

### Step 3: Write task.toml

Minimal configuration:

```toml title="task.toml"
version = "1.0"

[metadata]
name = "my-eval"

[agent]
timeout_sec = 900
```

See [Task Configuration](task-toml.md) for all options.

### Step 4: Run

```bash
inspect-coco run my-eval/
```

## Design principles

### One eval, one behavior

Each eval tests exactly one thing. Do not combine "create a file AND fix a bug AND run tests" into a single task. Split them:

```
evals/
├── create-config-file/     # tests: can agent create config?
├── fix-import-error/       # tests: can agent fix imports?
└── run-test-suite/         # tests: can agent run pytest?
```

This gives you:

- Clear failure signals (you know which behavior broke)
- Parallel execution (faster feedback)
- Easy addition and removal of individual tests

### Starter files

If the agent needs existing files to work with (code to fix, config to modify), place them in a `starter/` directory:

```
fix-import-error/
├── task.toml
├── instruction.md
├── starter/
│   └── app.py          # (1)!
└── tests/
    └── test.sh
```

1. This broken file gets copied to `/workspace/app.py` before the agent runs.

Files in `starter/` are copied to `/workspace/` before the agent starts.

### Custom Docker environment

If your eval needs specific tools or services, add a `compose.yaml`:

```yaml title="compose.yaml"
services:
  default:  # (1)!
    build:
      context: ../../src/inspect_coco/sandbox
      dockerfile: Dockerfile
    init: true
    command: ["tail", "-f", "/dev/null"]
    environment:
      - DATABASE_URL=postgres://localhost/test
```

1. The service **must** be named `default`. Inspect requires this convention.

## Scaffolding from a plugin

If you have a CoCo plugin with skills, the scaffold command auto-generates evals:

```
$inspect-coco:scaffold
```

It reads your `.cortex-plugin/plugin.json`, finds leaf skills (skipping routers), and creates one eval per skill with IDD-structured instructions.
