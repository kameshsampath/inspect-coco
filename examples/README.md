# Examples

Working eval tasks demonstrating inspect-coco end-to-end.

## Prerequisites

- Docker running
- `~/.snowflake/connections.toml` with a valid JWT or PAT connection
- `cortex exec --help` works (beta channel)
- Package installed: `uv add git+https://github.com/kameshsampath/inspect-coco.git`

## Configuration

Create a `.env` file in the project root with your connection name:

```bash
cp .env.example .env
```

Then set `INSPECT_COCO_SNOWFLAKE_CONNECTION` to one of your configured connections:

```dotenv
INSPECT_COCO_SNOWFLAKE_CONNECTION=my-connection
```

> [!NOTE]
> Run `grep "^\[" ~/.snowflake/connections.toml` to see available connections.
> If you don't set this, the resolver looks for a connection named `default`.

## Running Examples

### Using `inspect-coco` CLI (recommended)

```bash
# Check IDD scores for all examples (no Docker needed)
inspect-coco idd-check examples/

# Run all examples as a suite (uses suite.yaml)
inspect-coco run examples/

# Dry-run to see what would execute
inspect-coco run examples/ --dry-run

# Run a single example
inspect-coco run examples/hello-world

# Override epochs
inspect-coco run examples/hello-world --epochs 5
```

### Using `inspect eval` directly

> [!NOTE]
> With the removal of `task.py`, direct `inspect eval` usage is no longer
> supported. Use `inspect-coco run` which calls Inspect's eval API in-process.

## Example Tasks

| Example | What It Tests | IDD Score |
|---------|--------------|-----------|
| `hello-world` | Basic file creation | 1.0 |
| `fix-syntax-errors` | Code repair (uses starter/ files) | 1.0 |
| `custom-compose` | Custom Docker env with environment variables | 1.0 |
| `test-suite` | Pytest with multiple test functions | 1.0 |
| `low-idd-score` | What happens with a vague instruction (IDD warning demo) | 0.25 |

## Task Structure

Each example follows the atomic eval pattern (one skill, one behavior):

```text
example-name/
├── task.toml          # Config: timeout, epochs, IDD threshold
├── instruction.md     # Agent prompt (IDD-structured)
├── tests/
│   ├── test.sh        # Bash verification (exit 0 = pass)
│   └── test_*.py      # Or pytest tests (see test-suite example)
├── starter/           # Optional: files copied to /workspace before agent runs
└── compose.yaml       # Optional: custom Docker Compose (overrides builtin)
```

> [!TIP]
> Use `[environment].test_cmd` in task.toml to run pytest directly:
> ```toml
> [environment]
> test_cmd = "pytest /workspace/tests/ -v"
> ```

## Running a Test Suite

The recommended way to run all evals is via `suite.yaml`:

```bash
# Uses suite.yaml to discover and run all tasks
inspect-coco run examples/
```

Or run individual tasks:

```bash
inspect-coco run examples/hello-world
inspect-coco run examples/fix-syntax-errors
```

## Viewing Results

Eval results are saved as `.eval` log files in `logs/`. Use Inspect's
tools to view them.

```bash
# Open the web viewer (serves all logs in logs/)
inspect view

# List recent eval logs
inspect log list

# Dump a log as JSON to terminal
inspect log dump logs/<log-file>.eval

# Convert to JSON file for scripting
inspect log convert logs/<log-file>.eval --to json
```

> [!TIP]
> Install the [Inspect AI VS Code extension](https://marketplace.visualstudio.com/items?itemName=UKAISafetyInstitute.inspect-ai)
> for in-editor log viewing with the Transcript tab.

The log viewer shows:
- Pass/fail per epoch (pass@k)
- Full conversation transcript (messages, tool calls)
- Token usage and timing
- Scorer output (test.sh stdout/stderr)

## Writing Your Own

Use the `create-task` CoCo skill for guided creation:

```text
$inspect-coco:create-task
```

Or see [Writing Evals](../docs/writing-evals.md) for the manual approach.
