# Metrics and Reporting

inspect-coco reports two scorer results in every eval run. Each scorer produces its own metrics that appear in the eval summary and log viewer.

## Scorers

### verification

Runs the test command (`tests/test.sh` or a custom `test_cmd`) inside the Docker sandbox after the agent completes. Exit code 0 means pass, non-zero means fail.

| Metric | Type | Meaning |
|--------|------|---------|
| `passed` | count | Number of epochs where the test passed |
| `total` | count | Total number of epochs scored |

The pass rate across epochs is your **pass@k** consistency signal.

!!! example "Reading pass@k"

    With `epochs: 3`:

    - `passed=3 total=3` means the agent succeeded every time. Reliable.
    - `passed=1 total=3` means flaky behavior. Likely a vague instruction.
    - `passed=0 total=3` means broken. Check your test script first.

### idd_quality

Scores the instruction quality using the IDD rubric. This runs once per sample and does not depend on sandbox execution. It reports how well-structured the prompt is before the agent even starts.

| Metric | Type | Meaning |
|--------|------|---------|
| `idd_score` | float (0.0 to 1.0) | Average IDD quality score |

The score metadata also includes a per-dimension breakdown:

| Dimension | What it checks |
|-----------|---------------|
| `idd_goal` | Presence and clarity of a Goal section |
| `idd_requirements` | Presence of intent-based requirements |
| `idd_constraints` | Presence of scope and safety constraints |
| `idd_output` | Presence of verifiable success criteria |

## Interpreting results

| verification | idd_quality | Diagnosis |
|:---:|:---:|---|
| 3/3 | >= 0.8 | Healthy eval. Instruction is clear and agent is consistent. |
| 1/3 or 2/3 | >= 0.8 | Agent issue. Instruction is good but agent behavior varies. |
| 1/3 or 2/3 | < 0.6 | Instruction issue. Improve the prompt using IDD template. |
| 0/3 | any | Broken test or unsolvable task. Check test.sh logic first. |

!!! tip "The hypothesis"

    High IDD score predicts high pass@k. Over time, you will see that tasks scoring above 0.8 on IDD pass consistently (3/3), while tasks below 0.5 are flaky (1/3 or 2/3).

## Viewing results

After running `inspect-coco run`, use Inspect's built-in tools:

```bash
# Open the web viewer (serves all logs)
inspect view

# List recent eval logs
inspect log list

# Dump a specific log as JSON
inspect log dump logs/<log-file>.eval
```

The log viewer shows both scorers side by side with full conversation transcripts, token usage, and timing data.

## Configuration

Control epochs in `task.toml`:

```toml title="task.toml"
[metadata]
epochs = 3          # number of repetitions for pass@k
idd_threshold = 0.6 # minimum IDD score before warning
```

Or override via CLI:

```bash
inspect-coco run examples/ --epochs 5
```
