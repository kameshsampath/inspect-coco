# CLI Reference

`inspect-coco` provides three commands for working with CoCo skill evaluations.

## Global Options

```
inspect-coco [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose  Enable debug logging.
  --help         Show this message and exit.
```

## Commands

### `run` — Execute Evaluations

Run eval suites or individual tasks.

```bash
inspect-coco run <PATH> [OPTIONS]
```

PATH can be:
- A suite directory (containing `suite.yaml`)
- A parent directory (finds all `suite.yaml` recursively)
- A single task directory (containing `task.toml`)

**Options:**

| Flag | Description |
|------|-------------|
| `--task PATH` | Run a specific task directory |
| `--epochs INT` | Override epochs (pass@k) |
| `--model TEXT` | Override CoCo model |
| `--connection TEXT` | Override Snowflake connection name |
| `--limit INT` | Limit samples per task (for quick tests) |
| `--dry-run` | Show what would run without executing |

**Examples:**

```bash
# Run all suites under evals/
inspect-coco run evals/

# Run a single task
inspect-coco run evals/my-skill/basic-prompt

# Override epochs and preview
inspect-coco run evals/ --epochs 5 --dry-run

# Use a specific Snowflake connection
inspect-coco run evals/ --connection devrel-ent
```

### `idd-check` — Score Instruction Quality

Check IDD (Intent-Driven Development) scores for task instructions without
running any evaluations. Reports per-criterion scores and provides feedback
for instructions below the threshold.

```bash
inspect-coco idd-check <PATH> [OPTIONS]
```

PATH can be a single task directory or a parent directory (searches recursively
for `instruction.md` files).

**Options:**

| Flag | Description |
|------|-------------|
| `--threshold FLOAT` | IDD score threshold (default: 0.6) |

**Examples:**

```bash
# Check all instructions under evals/
inspect-coco idd-check evals/

# Check a single task
inspect-coco idd-check evals/my-skill/basic-prompt

# Stricter threshold
inspect-coco idd-check evals/ --threshold 0.8
```

**Output:**

```
PASS my-skill (score: 0.85)
  Goal: 1.00  Requirements: 0.80
  Constraints: 0.80  Output: 0.80
  Ambiguity words: 2  Specificity: 0.85

FAIL vague-task (score: 0.25)
  Goal: 0.00  Requirements: 0.50
  Constraints: 0.00  Output: 0.50
  Ambiguity words: 7  Specificity: 0.00

  Feedback:
    [IDD Pre-Check] Score: 0.25 / 1.0 (BELOW THRESHOLD)
    ...
```

Exit code 1 if any instruction is below the threshold. Use in CI to gate
eval runs on instruction quality.

### `scaffold` — Generate Eval Suites

Scan a CoCo plugin project and auto-generate eval suites for each leaf skill.

```bash
inspect-coco scaffold [OPTIONS]
```

**Options:**

| Flag | Description |
|------|-------------|
| `--plugin-dir PATH` | Skills directory to scan (default: auto-detect) |
| `--output-dir PATH` | Output directory (default: `evals`) |
| `--skill TEXT` | Only scaffold these skills (repeatable) |
| `--ignore TEXT` | Extra ignore patterns (repeatable) |
| `--dry-run` | Show what would be generated without writing |

**Examples:**

```bash
# Auto-detect plugin and generate evals
inspect-coco scaffold

# Preview what would be generated
inspect-coco scaffold --dry-run

# Only scaffold specific skills
inspect-coco scaffold --skill create-task --skill deploy

# Custom output directory
inspect-coco scaffold --output-dir tests/evals
```

**What it generates:**

```
evals/<skill-name>/
  suite.yaml                  # Suite config (auto-discovery, defaults)
  basic-prompt/
    task.toml                 # Config (timeout, epochs, IDD threshold)
    instruction.md            # IDD-structured instruction (Goal/Req/Con/Out)
    tests/
      test.sh                 # Verification script (placeholder)
```

After scaffolding:
1. Edit `tests/test.sh` with actual verification logic
2. Refine the Output section in `instruction.md`
3. Run `inspect-coco idd-check evals/` to validate
4. Run `inspect-coco run evals/ --dry-run` to preview

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failure (test failed, IDD below threshold, no tasks found) |
