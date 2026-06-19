# task.toml Reference

Every eval task has a `task.toml` file that controls how it runs.

## Minimal Example

```toml
version = "1.0"

[metadata]
name = "my-task"

[agent]
timeout_sec = 900
```

That's it. Everything else has sensible defaults.

## Full Example (annotated)

```toml
version = "1.0"

[metadata]
name = "my-task"
description = "What this eval tests"

# Run the task 3 times to measure consistency (pass@k)
epochs = 3

# Instruction quality threshold. Below this = warning before running.
idd_threshold = 0.6

# Set to true to block execution when instruction quality is low
idd_strict = false

[agent]
# How long cortex exec can run (seconds)
timeout_sec = 900

# Maximum tool-use turns before stopping
max_turns = 30

# Override model (default: CoCo auto mode picks the best model)
# model = "claude-sonnet-4-5"

# Snowflake connection name from your connections.toml
# connection = "default"

# Working directory inside the Docker container
workdir = "/workspace"

# Disable specific bundled skills during this eval
# remove_skills = ["developing-with-streamlit-in-snowflake"]

[environment]
# Custom test command (default: bash /workspace/tests/test.sh)
# test_cmd = "pytest /workspace/tests -v"

# How long the test script can run (seconds)
test_timeout = 300

# Custom Docker Compose file (relative to task directory)
# compose = "compose.yaml"
```

## Sections

### `[metadata]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | directory name | Identifier shown in results |
| `description` | string | - | Human-readable explanation |
| `epochs` | int | 3 | Number of runs for consistency |
| `idd_threshold` | float | 0.6 | Minimum instruction quality score |
| `idd_strict` | bool | false | Fail (not just warn) on low score |

### `[agent]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout_sec` | int | 900 | Agent execution timeout |
| `max_turns` | int | - | Cap on tool-use turns |
| `model` | string | - | Model override (omit for auto) |
| `connection` | string | - | Named Snowflake connection |
| `workdir` | string | /workspace | Container working directory |
| `remove_skills` | list | - | Skills to disable |

### `[environment]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `test_cmd` | string | `bash /workspace/tests/test.sh` | Verification command |
| `test_timeout` | int | 300 | Test execution timeout |
| `compose` | string | - | Custom compose file path |

## Epochs and Consistency

Epochs control how many times the same task runs. This measures pass@k:

- `epochs = 1` - single run, no consistency data
- `epochs = 3` - default, basic consistency signal
- `epochs = 5` - stronger signal, slower

Example: if a task passes 2 out of 3 epochs, the pass rate is 66%.
A well-written instruction (high IDD score) should pass all epochs consistently.

> [!IMPORTANT]
> Higher epochs mean longer total run time. Each epoch runs the full
> agent + test cycle. A 900s timeout task with 5 epochs could take up
> to 75 minutes.

## File Structure

```
my-task/
├── task.toml          # This file
├── instruction.md     # Agent prompt (IDD-structured)
├── tests/
│   └── test.sh        # Verification (exit 0 = pass)
├── starter/           # Optional: files copied to /workspace
└── compose.yaml       # Optional: custom Docker environment
```

## Custom Docker Compose

If your eval needs extra services (database, API mock) or custom environment
variables, add a `compose.yaml` in the task directory. Inspect auto-discovers it.

```yaml
services:
  default:
    build:
      context: ../../src/inspect_coco/sandbox
      dockerfile: Dockerfile
    init: true
    command: ["tail", "-f", "/dev/null"]
    environment:
      - MY_CUSTOM_VAR=some-value
```

> [!NOTE]
> The service must be named `default`. Inspect uses this name to find the primary sandbox.
