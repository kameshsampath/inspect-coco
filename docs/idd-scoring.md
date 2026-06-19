# IDD Scoring

Every instruction.md is scored before the eval runs.
This catches poorly-written instructions early and teaches you to write
better ones.

## What is IDD?

IDD (Intent-Driven Development) is a principle: express what you want as a
clear intent, not as step-by-step commands. For eval instructions, this means
structured prompts produce more consistent results than vague ones.

## The Template

A well-structured instruction has four parts:

```markdown
## Goal
What should exist after the agent finishes.

## Requirements
What the agent must do (stated as intent, not commands).

## Constraints
What the agent must NOT do. Boundaries and scope.

## Output
How we verify success. Concrete, testable conditions.
```

## How Scoring Works

The scorer checks four dimensions (0.25 weight each):

| Criterion | What It Looks For |
|-----------|-------------------|
| Goal | Section header or phrases like "create a", "produce a", "desired outcome" |
| Requirements | "must", "should", "shall", intent-language patterns |
| Constraints | "do not", "must not", "avoid", "only use", scope boundaries |
| Output | "success", "verify", "file exists", "test passes", concrete conditions |

Total score: 0.0 to 1.0

The scorer also flags vague words ("appropriate", "properly", "handle", "good") that reduce determinism.

## Example: Good vs Bad

**Scores 1.0:**

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

**Scores 0.2:**

```
Make a JSON file with some data. It should be properly formatted and have
appropriate content. Handle edge cases.
```

The second instruction will produce inconsistent results across runs
because the agent has to guess what "appropriate content" and "edge cases" mean.

## Threshold Behavior

Default threshold: 0.6

| Score | Behavior |
|-------|----------|
| >= threshold | Eval runs normally. "PASS" logged. |
| < threshold (default) | Warning printed with suggestions. Eval still runs. |
| < threshold + `idd_strict = true` | Eval fails with error. Must fix instruction first. |

## The Feedback

When an instruction is below threshold, you get actionable feedback:

```
[IDD Pre-Check] Score: 0.45 / 1.0 (BELOW THRESHOLD, threshold: 0.6)

  + Goal: Weak goal signal: 'generate a'. Consider adding an explicit Goal section.
  + Requirements: Some requirements found: must, requirement
  - Constraints: No constraints defined. Agent may take unexpected paths.
    -> Add: "[Constraints] Do not modify X / Only use Y / Scope limited to Z"
  + Output: Output indicators found: result, returns

  IDD Template:
    [Goal]         — desired outcome / desired state
    [Requirements] — intent statements (not steps)
    [Constraints]  — scope, safety, what not to do
    [Output]       — verifiable success criteria

  Tip: Use $inspect-coco:create-task for guided IDD-structured task creation.
```

Each missing criterion gets a concrete suggestion you can copy into your instruction.

## Why This Matters

The hypothesis: **high IDD score predicts high pass@k.**

When you run with epochs (default: 3), you get consistency data. Over time,
you'll see that tasks with IDD score > 0.8 pass consistently (3/3), while
tasks with score < 0.5 are flaky (1/3 or 2/3).

This gives you a fast signal: if the IDD score is low, fix the instruction before running expensive eval cycles.

## Configuring

In `task.toml`:

```toml
[metadata]
idd_threshold = 0.6   # minimum score to proceed
idd_strict = false    # true = fail instead of warn
```

Or via CLI:

```bash
inspect-coco run my-task/ --epochs 3
```
