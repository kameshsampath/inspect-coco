# task.toml Specification

Configuration file for inspect-coco eval tasks.

## Format

```toml
version = "1.0"

[metadata]
name = "my-task"                    # Task identifier
description = "What this tests"     # Human-readable description
epochs = 3                          # Runs for pass@k consistency (default: 3)
idd_threshold = 0.6                 # IDD score minimum (default: 0.6)
idd_strict = false                  # true = fail below threshold (default: warn)

[agent]
timeout_sec = 900                   # Max agent execution time (default: 900)
max_turns = 30                      # Safety ceiling for agentic turns
model = "claude-sonnet-4-5"         # Model override (default: auto mode)
connection = "default"              # Snowflake connection name
workdir = "/workspace"              # Working directory in sandbox
remove_skills = ["skill-name"]      # Bundled skills to disable

[environment]
compose = "path/to/compose.yaml"    # Custom compose file (optional)
test_cmd = "pytest /workspace/tests -v"  # Custom test command
test_timeout = 300                  # Test execution timeout (default: 300)
```

## Required Files

```
my-task/
├── task.toml          # This file
├── instruction.md     # Agent prompt (IDD-structured)
└── tests/
    └── test.sh        # Verification script (exit 0 = pass)
```

## Optional Files

```
my-task/
├── starter/           # Files copied to /workspace before agent runs
│   └── app.py         # (any file structure)
└── compose.yaml       # Custom Docker Compose (overrides builtin)
```

## Sandbox Resolution Order

1. `compose.yaml` in task directory (Inspect auto-discovers)
2. `[environment].compose` path in task.toml
3. Built-in inspect-coco sandbox (cortex CLI pre-installed)

## Epochs and Consistency

Epochs control pass@k measurement:
- `epochs = 1` — single run, no consistency data
- `epochs = 3` — default, measures basic consistency
- `epochs = 5` — stronger consistency signal

Higher epochs = more confidence in determinism but longer run time.
