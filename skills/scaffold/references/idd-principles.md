# IDD Principles for Eval Instructions

Intent-Driven Development (IDD) treats instructions as design artifacts. Well-structured intent produces deterministic agent outcomes.

## IDD Template

```
[Goal]         — desired outcome / desired state
[Requirements] — intent statements (not imperative steps)
[Constraints]  — scope, safety rules, what not to do
[Output]       — verifiable success criteria
```

## Why It Matters for Evals

- **High IDD score → high pass@k** — structured intent drives consistent results
- **Low IDD score → flaky evals** — vague instructions produce unpredictable behavior
- **The scorer validates** — inspect-coco scores every instruction before running

## Scoring Criteria (0.25 weight each)

| Criterion | What It Checks |
|-----------|---------------|
| Goal | Clear desired outcome present |
| Requirements | Intent statements (not imperative steps) |
| Constraints | Boundaries, what-not-to-do defined |
| Output | Verifiable success criteria |

## Good vs Bad

**Good (scores > 0.8):**
```markdown
## Goal
Create a Python file `/workspace/calc.py` with an add function.

## Requirements
- Must accept two numeric arguments
- Must return their sum

## Constraints
- Do not use external libraries
- Do not modify other files

## Output
- `/workspace/calc.py` exists
- `python -c "from calc import add; assert add(2,3)==5"` passes
```

**Bad (scores < 0.4):**
```
Make a calculator that works properly and handles edge cases appropriately.
```

## Key Principles

1. **Name the outcome, don't describe the process**
2. **Specify parameters, not procedures**
3. **Define boundaries explicitly**
4. **State verifiable conditions for success**

## Further Reading

- [Kamesh's IDD Blog Series](https://blogs.kameshs.dev)
- `$devops-coco-agents:idd-evaluate-prompt` — audit an instruction
- `$devops-coco-agents:idd-rewrite-prompt` — guided rewrite
