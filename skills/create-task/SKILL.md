---
name: inspect-coco-create-task
description: >
  Create a single eval task for a CoCo skill. Generates task.toml,
  IDD-structured instruction.md, and test.sh with guided prompts.
  Use when: "create eval task", "new eval", "add task", "write eval for skill",
  "test my skill", "add evaluation", "create test for skill".
---

## When to Load

Load when the user wants to:
- Create a single new eval task (not a full scaffold)
- Add an eval for a specific skill they're developing
- Write a test for a skill behavior

## Stopping Points

Before generating files, ask:
1. What skill/behavior are you testing?
2. What is the expected outcome (success criteria)?
3. Any specific constraints the agent should follow?

## Steps

### Step 1: Gather Intent

First, check `~/.snowflake/connections.toml` (honour `SNOWFLAKE_HOME` env var).
If there is no `[default]` section AND `INSPECT_COCO_SNOWFLAKE_CONNECTION` is not set in
the environment or `.env` file, ask which connection to use:

```
ask_user_question:
  header: "Connection"
  question: "No default connection found. Which connection should this eval use?"
  type: "options"
  options: <list section names from connections.toml that use JWT or PAT>
```

Then ask the user:

```
ask_user_question:
  header: "Eval Task"
  question: "What skill or behavior do you want to evaluate?"
  type: "text"
  defaultValue: "my-skill-name"
```

```
ask_user_question:
  header: "Success"
  question: "What does success look like? (What file exists, what output is produced?)"
  type: "text"
  defaultValue: "File /workspace/output.json exists with valid JSON"
```

### Step 2: Generate task.toml

```toml
version = "1.0"

[metadata]
name = "<task-name>"
description = "<from user input>"
epochs = 3
idd_threshold = 0.6

[agent]
timeout_sec = 900
max_turns = 30

[environment]
test_timeout = 300
```

### Step 3: Generate instruction.md (IDD Template)

Structure using IDD:

```markdown
## Goal

<Derived from user's intent — specific desired outcome>

## Requirements

- <Intent statement 1 from user input>
- <Intent statement 2>

## Constraints

- Do not modify files outside /workspace
- Do not install packages unless explicitly required
- <Additional constraints from user>

## Output

Success criteria:
- <Verifiable condition from user's success description>
```

### Step 4: Generate tests/test.sh

```bash
#!/bin/bash
set -e
# Verify the success criteria
<test commands derived from output section>
```

### Step 5: Validate

Run IDD scorer on the generated instruction:
```python
from inspect_coco.idd import score_instruction, explain_score
score = score_instruction(instruction_text)
print(explain_score(score))
```

If score < 0.6, suggest improvements before proceeding.

### Step 6: Confirm

Show the user the generated files and ask for confirmation before writing.

## References

- [IDD Principles](../scaffold/references/idd-principles.md)
- [task.toml Spec](../scaffold/references/task-toml-spec.md)
