# Metrics

inspect-coco reports two scorer results in every eval run. Each scorer
produces its own metrics that appear in the eval summary and log viewer.

## Scorers

### verification

Runs the test command (`tests/test.sh` or custom `test_cmd`) inside the
Docker sandbox after the agent completes. Exit code 0 = pass, non-zero = fail.

| Metric | Type | Meaning |
|--------|------|---------|
| `passed` | count | Number of samples (epochs) where the test passed |
| `total` | count | Total number of samples scored |

The pass rate across epochs is your **pass@k** consistency signal. For example,
with `epochs: 3`, seeing `passed=3 total=3` means the agent succeeded every time.
`passed=1 total=3` means flaky behavior (likely a vague instruction).

### idd_quality

Scores the instruction quality using the IDD rubric. Runs once per sample
(does not depend on sandbox execution). Reports how well-structured the
prompt is before the agent even starts.

| Metric | Type | Meaning |
|--------|------|---------|
| `idd_score` | float (0.0-1.0) | Average IDD quality score across samples |

The score metadata also includes per-dimension breakdown:
- `idd_goal` — presence and clarity of Goal section (0.0-1.0)
- `idd_requirements` — presence of intent-based requirements (0.0-1.0)
- `idd_constraints` — presence of scope/safety constraints (0.0-1.0)
- `idd_output` — presence of verifiable success criteria (0.0-1.0)
- `idd_passed` — whether score met the configured threshold

## Reading Results

After running `inspect-coco run`, use `inspect view` to open the log viewer.
The Scores tab shows both scorers side by side:

```
┌──────────────────────────────────────────────────────┐
│ verification                                         │
│   passed: 3    total: 3                              │
├──────────────────────────────────────────────────────┤
│ idd_quality                                          │
│   idd_score: 0.95                                    │
└──────────────────────────────────────────────────────┘
```

## Interpreting Results

| verification | idd_quality | Diagnosis |
|-------------|-------------|-----------|
| 3/3 passed | >= 0.8 | Healthy eval. Instruction is clear and agent is consistent. |
| 1/3 or 2/3 | >= 0.8 | Agent issue. Instruction is good but agent behavior is non-deterministic. |
| 1/3 or 2/3 | < 0.6 | Instruction issue. Improve the prompt structure using IDD template. |
| 0/3 passed | any | Broken test or unsolvable task. Check test.sh logic first. |

## Configuration

Control epochs (pass@k sample count) in `task.toml`:

```toml
[metadata]
epochs = 3          # default: 3 repetitions
idd_threshold = 0.6 # minimum IDD score before warning
```

Or override via CLI:

```bash
inspect-coco run examples/ --epochs 5
```

## Custom Metrics

Both scorers use Inspect AI's `@metric` decorator. You can add your own
custom metrics by writing a scorer in your project. See the
[Inspect AI metrics docs](https://inspect.ai-safety-institute.org.uk/scorers.html#built-in-metrics)
for the framework API.
