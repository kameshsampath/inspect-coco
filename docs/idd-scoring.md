# IDD Scoring

Every instruction is scored before the eval runs. This catches poorly-written instructions early and teaches you to write better ones.

## What is IDD?

IDD (Intent-Driven Development) is a principle: express what you want as a clear intent, not as step-by-step commands. For eval instructions, structured prompts produce more consistent results than vague ones.

## The template

A well-structured instruction has four parts:

```markdown title="instruction.md"
## Goal
What should exist after the agent finishes.

## Requirements
What the agent must do (stated as intent, not commands).

## Constraints
What the agent must NOT do. Boundaries and scope.

## Output
How we verify success. Concrete, testable conditions.
```

## How scoring works

The scorer checks four dimensions, each weighted at 0.25:

| Criterion | What it looks for |
|-----------|-------------------|
| Goal | Section header or phrases like "create a", "produce a", "desired outcome" |
| Requirements | "must", "should", "shall", intent-language patterns |
| Constraints | "do not", "must not", "avoid", "only use", scope boundaries |
| Output | "success", "verify", "file exists", "test passes", concrete conditions |

Total score ranges from 0.0 to 1.0.

The scorer also flags vague words ("appropriate", "properly", "handle", "good") that reduce determinism.

## Example: good vs. bad

??? success "Scores 1.0"

    ```markdown
    ## Goal
    Create a file `/workspace/result.json` with a JSON array of 3 items.

    ## Requirements
    - Each item must have "id" (integer) and "name" (string) fields
    - IDs must be sequential starting from 1

    ## Constraints
    - Do not use external libraries
    - Do not create any other files

    ## Output
    - `/workspace/result.json` exists
    - Content is valid JSON
    - Array has exactly 3 items with correct structure
    ```

??? failure "Scores 0.2"

    ```
    Make a JSON file with some data. It should be properly formatted and have
    appropriate content. Handle edge cases.
    ```

    This instruction produces inconsistent results across runs because the agent must guess what "appropriate content" and "edge cases" mean.

## Threshold behavior

Default threshold: **0.6**

| Score | Behavior |
|-------|----------|
| >= threshold | Eval runs normally. "PASS" logged. |
| < threshold (default mode) | Warning printed with suggestions. Eval still runs. |
| < threshold + `idd_strict = true` | Eval fails with error. Must fix instruction first. |

## Feedback output

When an instruction is below threshold, you get actionable feedback:

```
[IDD Pre-Check] Score: 0.45 / 1.0 (BELOW THRESHOLD, threshold: 0.6)

  + Goal: Weak goal signal. Consider adding an explicit Goal section.
  + Requirements: Some requirements found: must, requirement
  - Constraints: No constraints defined. Agent may take unexpected paths.
    -> Add: "[Constraints] Do not modify X / Only use Y / Scope limited to Z"
  + Output: Output indicators found: result, returns
```

Each missing criterion gets a concrete suggestion you can copy into your instruction.

## Configuring

In `task.toml`:

```toml title="task.toml"
[metadata]
idd_threshold = 0.6   # minimum score to proceed
idd_strict = false    # true = fail instead of warn
```

Or via CLI:

```bash
inspect-coco idd-check evals/ --threshold 0.8
```

!!! info "Why this matters"

    The hypothesis: **high IDD score predicts high pass@k.**

    When you run with epochs (default: 3), you get consistency data. Over time, you will see that tasks with IDD score above 0.8 pass consistently (3/3), while tasks below 0.5 are flaky (1/3 or 2/3).

    This gives you a fast signal: if the IDD score is low, fix the instruction before running expensive eval cycles.
