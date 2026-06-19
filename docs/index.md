# Inspect CoCo

**Deterministic skill evaluations for Cortex Code agents.**

inspect-coco measures whether your CoCo skills produce correct, consistent results. It runs your agent against structured instructions inside isolated Docker containers, scores the output with deterministic tests, and repeats the process to surface flaky behavior.

The core question it answers: *does this skill do the right thing every time?*

## How it works

```mermaid
flowchart TD
    A[instruction.md] --> B[IDD quality check]
    B --> C[Docker sandbox]
    C --> D[cortex exec]
    D --> E[test.sh]
    E --> F{pass/fail}
    F -->|repeat k times| C
    F --> G["pass@k score"]
```

1. Your **instruction** describes what the agent should accomplish, structured with Goal, Requirements, Constraints, and Output sections.
2. The **IDD scorer** checks instruction quality before running anything expensive.
3. A **Docker sandbox** provides a clean, isolated environment for each run.
4. The **CoCo agent** executes the instruction via `cortex exec`.
5. A **verification script** checks whether the agent produced the correct result.
6. **Epochs** repeat the process multiple times to measure consistency.

## Why structured instructions matter

Vague instructions produce inconsistent results. When you tell an agent to "set up the project properly," each run may take a different path. Structured instructions (IDD format) narrow the solution space so the agent converges on the same correct behavior across runs.

This is the hypothesis inspect-coco helps you validate: **high instruction quality predicts high pass@k consistency.**

## Quick start

```bash
# Install
uv add git+https://github.com/kameshsampath/inspect-coco.git

# Run the example evals
inspect-coco run examples/

# View results in the browser
inspect view
```

!!! tip "First time setup"

    See [Getting Started](getting-started.md) for prerequisites (Docker, Snowflake CLI, connection configuration) and a full walkthrough.

## What you get

- **Pass@k consistency scores** across repeated runs
- **IDD quality feedback** on your instructions before running expensive evals
- **Full transcripts** of every agent conversation (tool calls, responses, timing)
- **Scaffolding** that generates eval tasks from existing plugin structure
