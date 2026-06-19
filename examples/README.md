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

Then set `SNOWFLAKE_CONNECTION_NAME` to one of your configured connections:

```dotenv
SNOWFLAKE_CONNECTION_NAME=my-connection
```

> [!NOTE]
> Run `grep "^\[" ~/.snowflake/connections.toml` to see available connections.
> If you don't set this, the resolver looks for a connection named `default`.

## Running Examples

```bash
# Run a single example (point to the directory)
inspect eval examples/hello-world

# Run with specific model (default: CoCo auto mode)
inspect eval examples/hello-world --model cortex/claude-sonnet-4-5

# Run with more epochs for stronger consistency signal
inspect eval examples/hello-world --epochs 5

# Run multiple examples
inspect eval examples/hello-world examples/fix-syntax-errors

# Run all examples
inspect eval examples/*/task.py
```

> [!NOTE]
> Inspect discovers `task.py` in the directory automatically.
> Both `inspect eval examples/hello-world` and
> `inspect eval examples/hello-world/task.py` work.

## Example Tasks

| Example | What It Tests | IDD Score |
|---------|--------------|-----------|
| `hello-world` | Basic file creation | 1.0 |
| `fix-syntax-errors` | Code repair (uses starter/ files) | 1.0 |
| `custom-compose` | Custom Docker env with environment variables | 1.0 |

## Task Structure

Each example follows the atomic eval pattern (one skill, one behavior):

```text
example-name/
├── task.py            # Inspect entry point (@task function)
├── task.toml          # Config: timeout, epochs, IDD threshold
├── instruction.md     # Agent prompt (IDD-structured)
├── tests/
│   └── test.sh        # Verification (exit 0 = pass)
├── starter/           # Optional: files copied to /workspace before agent runs
└── compose.yaml       # Optional: custom Docker Compose (overrides builtin)
```

## Writing Your Own

Use the `create-task` CoCo skill for guided creation:

```text
$inspect-coco:create-task
```

Or see [Writing Evals](../docs/writing-evals.md) for the manual approach.

## Running a Test Suite

To run all evals in a directory as a suite:

```bash
# Run all examples
inspect eval examples/hello-world examples/fix-syntax-errors examples/custom-compose

# Or use a shell glob
inspect eval examples/*/task.py
```

Inspect runs tasks concurrently by default. Use `--max-tasks` to control parallelism:

```bash
inspect eval examples/*/task.py --max-tasks 2
```

## Viewing Results

Eval results are saved as `.eval` log files in `logs/`. These are binary
(compressed JSON) and need Inspect's tools to read.

```bash
# Open the web viewer (shows all logs in logs/)
inspect view

# View a specific log file
inspect view logs/2026-06-19T08-25-18_hello-world_abc123.eval

# List recent eval logs
inspect log list

# Print summary of a log to terminal
inspect log read logs/2026-06-19T08-25-18_hello-world_abc123.eval
```

> [!TIP]
> Install the [Inspect AI VS Code extension](https://marketplace.visualstudio.com/items?itemName=UKAISafetyInstitute.inspect-ai)
> for in-editor log viewing with the Transcript tab.

The log viewer shows:
- Pass/fail per epoch (pass@k)
- Full conversation transcript (messages, tool calls)
- Token usage and timing
- Scorer output (test.sh stdout/stderr)
