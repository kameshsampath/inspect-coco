# Suite Configuration

A `suite.yaml` groups multiple eval tasks under a shared configuration.
Use suites to organize evaluations per-skill with consistent defaults.

!!! tip "Editor autocomplete"

    Add this comment to the top of your suite.yaml for IDE validation and autocomplete:

    ```yaml
    # yaml-language-server: $schema=https://raw.githubusercontent.com/kameshsampath/inspect-coco/main/schemas/suite.schema.json
    ```

## File Location

Place `suite.yaml` at the root of your eval directory:

```
evals/
  my-skill/
    suite.yaml          # suite config for my-skill
    basic-prompt/
      task.toml
      instruction.md
      tests/test.sh
    edge-case/
      task.toml
      instruction.md
      tests/test.sh
```

## Schema

```yaml
name: my-skill-evals
description: Eval scenarios for the my-skill CoCo skill
skill: my-skill  # optional, links suite to a CoCo skill

defaults:
  epochs: 3            # pass@k consistency runs
  timeout_sec: 900     # agent timeout
  max_turns: null      # no turn limit
  idd_threshold: 0.6   # minimum IDD score
  idd_strict: false    # warn vs fail
  model: null          # use default model
  connection: null     # use default connection

# Auto-discover subdirectories with task.toml
tasks: auto

# Or list tasks explicitly with per-task overrides:
# tasks:
#   - path: basic-prompt
#   - path: edge-case
#     epochs: 5
#     timeout_sec: 1200

exclude:
  - drafts  # skip directories matching these prefixes
```

## Task Discovery

When `tasks: auto` (the default), the suite loader searches recursively for
subdirectories containing `task.toml`. Directories matching `exclude` patterns
are skipped.

## Glob Patterns

Explicit task lists support fnmatch patterns to match multiple directories at once:

```yaml title="suite.yaml"
tasks:
  - "basic-*"           # matches basic-prompt, basic-edge, etc.
  - path: "edge-*"
    epochs: 5           # override applied to all matched tasks
```

Patterns use Python's `fnmatch` syntax:

| Pattern | Matches |
|---------|---------|
| `*` | Everything |
| `basic-*` | basic-prompt, basic-edge, basic-foo |
| `test-?` | test-a, test-b (single character) |
| `[abc]-*` | a-task, b-task, c-task |

!!! note

    Patterns are matched against the relative path from the suite root.
    The `exclude` list is applied before pattern matching.

## Merge Priority

Configuration values are resolved in this order (highest wins):

1. CLI flags (`--epochs`, `--model`, `--connection`)
2. `task.toml` values
3. Suite per-task overrides (explicit tasks list)
4. Suite `defaults` section
5. Built-in defaults (epochs=3, timeout_sec=900, idd_threshold=0.6)

## CLI Usage

```bash
# Run all tasks in a suite
inspect-coco run evals/my-skill/

# Run all suites under a parent directory
inspect-coco run evals/

# Override epochs from CLI
inspect-coco run evals/my-skill/ --epochs 5

# Dry run to see what would execute
inspect-coco run evals/my-skill/ --dry-run

# Check IDD scores only (no eval execution)
inspect-coco idd-check evals/my-skill/
```
